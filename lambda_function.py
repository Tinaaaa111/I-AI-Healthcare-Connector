import json, boto3, io, unicodedata, base64
from fpdf import FPDF
from datetime import datetime

# --- CONFIG ---
REGION = "us-west-2"
BUCKET = "syntheademodata"
PROCESSED_PREFIX = "processed/"

# --- CLIENTS ---
s3 = boto3.client("s3", region_name=REGION)
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

# --- CORS HEADERS ---
def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,Accept",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
    }

# --- UTILITIES ---
def s3_read_text(key):
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        return obj["Body"].read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f" Error reading {key}: {e}")
        return ""

def clean_text(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    return text.encode("latin-1", "replace").decode("latin-1")

# --- BEDROCK CALL ---
def ask_bedrock(system_prompt, user_prompt):
    model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
        ],
        "max_tokens": 700,
        "temperature": 0.2
    }
    try:
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json"
        )
        result = json.loads(response["body"].read())
        if "content" in result and isinstance(result["content"], list):
            return "".join(p.get("text", "") for p in result["content"] if "text" in p)
        return result.get("output_text", "No valid response text found.")
    except Exception as e:
        print(f" Bedrock error: {e}")
        raise

# --- PATIENT HELPERS ---
def list_patients_from_processed():
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=PROCESSED_PREFIX)
    if "Contents" not in resp:
        return []
    patient_ids = set()
    for obj in resp["Contents"]:
        parts = obj["Key"].split("/")
        if len(parts) > 2 and parts[1]:
            patient_ids.add(parts[1])
    return [{"id": pid, "name": pid} for pid in sorted(patient_ids)]

def find_patient_folder(pid):
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=PROCESSED_PREFIX)
    for obj in resp.get("Contents", []):
        folder = obj["Key"].split("/")[1]
        if pid in folder or folder.startswith(pid.split("_")[0]):
            return folder
    return pid

# --- SMART FILE FILTER ---
def infer_relevant_csvs(question):
    q = question.lower()
    mapping = {
        "encounter": ["encounter.csv"],
        "hospital": ["encounter.csv", "organization.csv"],
        "visit": ["encounter.csv", "organization.csv"],
        "lab": ["observation.csv", "diagnosticreport.csv"],
        "medication": ["medication.csv", "medicationrequest.csv", "medicationadministration.csv"],
        "condition": ["condition.csv", "allergyintolerance.csv"],
        "procedure": ["procedure.csv"],
        "immunization": ["immunization.csv"],
        "organization": ["organization.csv"],
        "provider": ["practitioner.csv"],
        "patient": ["patient.csv"]
    }
    matched = set()
    for key, files in mapping.items():
        if key in q:
            matched.update(files)
    if not matched:
        matched.update(["encounter.csv", "condition.csv", "observation.csv"])
    print(f" Selected CSVs for question '{question}': {matched}")
    return list(matched)

def format_explain_predict(answer_text):
    txt = answer_text.strip()
    txt = txt.split("Prediction:")[0].strip()
    if "Explanation:" not in txt:
        txt = f"Explanation:\n{txt}"
    return txt

# --- HANDLERS ---
def handle_list_patients():
    pts = list_patients_from_processed()
    return {"statusCode": 200, "headers": cors_headers(), "body": json.dumps({"patients": pts})}

def handle_general(event):
    body = json.loads(event.get("body", "{}"))
    q = body.get("question")
    tone = body.get("tone", "patient")
    if not q:
        return {"statusCode": 400, "headers": cors_headers(), "body": json.dumps({"error": "Missing question"})}
    style = "Use simple, empathetic language." if tone == "patient" else "Use concise professional language."
    system_prompt = (
        "You are a safe, trustworthy health educator. "
        "Provide accurate, easy-to-understand general health information. "
        "Do not give diagnoses or treatment. " + style
    )
    raw = ask_bedrock(system_prompt, q)
    answer = format_explain_predict(raw)
    return {"statusCode": 200, "headers": cors_headers(), "body": json.dumps({"answer": answer})}

def handle_ask(event):
    body = json.loads(event.get("body", "{}"))
    pid = body.get("patientId")
    q = body.get("question")
    tone = body.get("tone", "patient")

    if not q:
        return {"statusCode": 400, "headers": cors_headers(), "body": json.dumps({"error": "Missing question"})}
    if not pid:
        return handle_general(event)

    folder = find_patient_folder(pid)
    print(f"🩺 Using folder: {folder}")

    ctx_parts = []
    try:
        resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{PROCESSED_PREFIX}{folder}/")
        files = [obj["Key"] for obj in resp.get("Contents", []) if obj["Key"].endswith(".csv")]
        print(f" Found {len(files)} CSVs for {pid}")

        selected = infer_relevant_csvs(q)
        for f in files:
            if any(sel.lower() in f.lower() for sel in selected):
                data = s3_read_text(f)
                if not data.strip():
                    continue
                sample = "\n".join(data.splitlines()[:50])
                ctx_parts.append(f"### {f.split('/')[-1]}\n{sample}")
    except Exception as e:
        ctx_parts.append(f" Error loading patient files: {e}")

    context = "\n\n".join(ctx_parts) or "No patient data found."

    # Truncate if too long for Claude
    if len(context) > 50000:
        context = context[:50000] + "\n\n[Note: patient data truncated for size limit]"

    style = "Use simple, empathetic language." if tone == "patient" else "Use concise professional language."
    system_prompt = (
        "You are a clinical AI assistant. Analyze available patient data (encounters, conditions, "
        "observations, medications, diagnostics, etc.) and summarize insights related to the question. "
        "If data was truncated or incomplete, acknowledge that clearly. " + style
    )
    try:
        response_text = ask_bedrock(system_prompt, f"Context:\n{context}\n\nQuestion: {q}")
        formatted = format_explain_predict(response_text)
        return {"statusCode": 200, "headers": cors_headers(), "body": json.dumps({"answer": formatted})}
    except Exception as e:
        print(" Bedrock or context error:", e)
        return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": str(e), "answer": f"⚠️ Lambda error: {str(e)}"})}

def handle_generate_pdf(event):
    try:
        body = json.loads(event.get("body", "{}"))
        content = body.get("content", "")
        if not content:
            return {"statusCode": 400, "headers": cors_headers(), "body": json.dumps({"error": "No content provided"})}
        filename = f"IAI_Report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        safe_content = clean_text(content)
        if len(safe_content) > 40000:
            safe_content = safe_content[:40000] + "\n\n(Truncated for size limit)"
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "I AI Healthcare Connector — Report", ln=True, align="C")
        pdf.ln(8)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 8, safe_content)
        pdf_bytes = pdf.output(dest="S").encode("latin-1", "ignore")
        b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        return {"statusCode": 200, "headers": {**cors_headers(), "Content-Type": "application/json"}, "body": json.dumps({"file": b64, "filename": filename})}
    except Exception as e:
        print(" PDF generation error:", e)
        return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": "Failed to generate PDF", "details": str(e)})}

# --- MAIN HANDLER ---
def lambda_handler(event, context):
    print(" Incoming event:", json.dumps(event)[:500])
    method = event.get("requestContext", {}).get("http", {}).get("method", event.get("httpMethod", "GET"))
    path = event.get("rawPath") or event.get("path", "/")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": cors_headers(), "body": ""}
    if method == "GET" and path in ["/", "/patients"]:
        return handle_list_patients()
    if method == "POST" and path == "/general":
        return handle_general(event)
    if method == "POST" and path == "/ask":
        return handle_ask(event)
    if method == "POST" and path in ["/pdf", "/order-pdf"]:
        return handle_generate_pdf(event)

    return {"statusCode": 404, "headers": cors_headers(), "body": json.dumps({"error": f"Not found for {method} {path}"})}

