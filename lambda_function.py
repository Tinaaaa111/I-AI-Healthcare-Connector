import json, boto3, io, csv, unicodedata, base64
import pandas as pd
from fpdf import FPDF
from datetime import datetime

# ---- CONFIG ----
REGION = "us-west-2"
BUCKET = "syntheademodata"
PROCESSED_PREFIX = "processed/"

# ---- CLIENTS ----
s3 = boto3.client("s3", region_name=REGION)
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

# ---- HELPERS ----
def s3_read_text(key):
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        return obj["Body"].read().decode("utf-8", errors="ignore")
    except Exception as e:
        if "NoSuchKey" not in str(e):
            print(f"⚠️ Error reading {key}: {e}")
        return ""

def clean_text(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("latin-1", "replace").decode("latin-1")
    return text

# ---- CORE DATA HELPERS ----
def list_patients_from_processed():
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=PROCESSED_PREFIX)
    if "Contents" not in resp:
        return []
    patient_ids = set()
    for obj in resp["Contents"]:
        parts = obj["Key"].split("/")
        if len(parts) > 2 and parts[1]:
            patient_ids.add(parts[1])

    patients = []
    for pid in sorted(patient_ids):
        csv_data = s3_read_text(f"{PROCESSED_PREFIX}{pid}/patients.csv") or s3_read_text(f"{PROCESSED_PREFIX}{pid}/patient.csv")
        name = pid
        try:
            rows = list(csv.reader(io.StringIO(csv_data)))
            if len(rows) > 1 and "name" in rows[0]:
                name = rows[1][rows[0].index("name")]
        except Exception:
            pass
        patients.append({"id": pid, "name": name})
    return patients

def summarize_hospitals_and_departments(pid):
    key = f"{PROCESSED_PREFIX}{pid}/encounters.csv"
    data = s3_read_text(key)
    if not data:
        return "⚠️ No encounter data available."
    try:
        df = pd.read_csv(io.StringIO(data))
    except Exception as e:
        return f"⚠️ Error reading encounters.csv: {e}"
    df.columns = [c.lower() for c in df.columns]
    if "serviceprovider" not in df.columns:
        return "⚠️ Missing hospital/provider info."
    if "class" not in df.columns:
        df["class"] = "Unknown"
    grouped = df.groupby(["serviceprovider", "class"]).size().reset_index(name="visits")
    lines = ["📍 Encounter Summary by Hospital and Department:"]
    for _, r in grouped.iterrows():
        lines.append(f"- {r['serviceprovider']} → {r['class']}: {r['visits']} visit(s)")
    return "\n".join(lines)

def analyze_trends(pid):
    base = f"{PROCESSED_PREFIX}{pid}/"
    sections, missing = [], []
    vitals_data = s3_read_text(base + "vitals.csv")
    if vitals_data:
        try:
            df = pd.read_csv(io.StringIO(vitals_data))
            df.columns = [c.lower() for c in df.columns]
            numeric_cols = [c for c in df.columns if df[c].dtype in ["float64", "int64"]]
            vitals = []
            for col in numeric_cols:
                s = df[col].dropna()
                if len(s) >= 2:
                    t = "increasing" if s.iloc[-1] > s.iloc[0] else "decreasing"
                    vitals.append(f"- {col.title()} is {t} ({s.iloc[0]} → {s.iloc[-1]})")
            if vitals:
                sections.append("📈 Vitals Trends:\n" + "\n".join(vitals))
        except Exception as e:
            missing.append(str(e))
    labs_data = s3_read_text(base + "labs.csv")
    if labs_data:
        try:
            df = pd.read_csv(io.StringIO(labs_data))
            df.columns = [c.lower() for c in df.columns]
            num_cols = [c for c in df.columns if df[c].dtype in ["float64", "int64"]]
            labs = []
            for col in num_cols:
                s = df[col].dropna()
                if len(s) >= 2:
                    t = "increasing" if s.iloc[-1] > s.iloc[0] else "decreasing"
                    labs.append(f"- {col.title()} is {t} ({s.iloc[0]} → {s.iloc[-1]})")
            if labs:
                sections.append("🧪 Lab Trends:\n" + "\n".join(labs))
        except Exception as e:
            missing.append(str(e))
    return "\n\n".join(sections) or "⚠️ No trend data."

def ask_bedrock(system_prompt, user_prompt):
    model = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "system": system_prompt,
        "messages": [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
        "max_tokens": 700,
        "temperature": 0.2
    }
    r = bedrock.invoke_model(modelId=model, body=json.dumps(body),
                             contentType="application/json", accept="application/json")
    res = json.loads(r["body"].read())
    return res["content"][0]["text"]

# ---- CORE HANDLERS ----
def handle_list_patients():
    pts = list_patients_from_processed()
    return {"statusCode": 200, "headers": {}, "body": json.dumps({"patients": pts})}

def handle_ask(event):
    body = json.loads(event.get("body", "{}"))
    role = body.get("role", "provider").lower()
    pid = body.get("patientId")
    q = body.get("question")

    if not q:
        return {"statusCode": 400, "headers": {}, "body": json.dumps({"error": "Missing question"})}

    # --- If the question doesn't reference a patient, treat it as general ---
    if not pid or "what is" in q.lower() or "explain" in q.lower() or "how does" in q.lower() or "difference" in q.lower():
        system_prompt = (
            "You are a general healthcare AI assistant. "
            "Answer clearly and accurately using medical knowledge, but keep the tone simple and educational. "
            "If the question is about medical terms, tests, or diseases, explain them concisely and safely."
        )
        answer = ask_bedrock(system_prompt, q)
        return {"statusCode": 200, "headers": {}, "body": json.dumps({"answer": answer})}

    # --- Otherwise, use patient-specific summarization ---
    ctx = []
    for n in ["patients.csv", "encounters.csv", "conditions.csv", "labs.csv", "vitals.csv", "imaging.csv"]:
        data = s3_read_text(f"{PROCESSED_PREFIX}{pid}/{n}")
        if data:
            ctx.append(f"## {n}\n{data[:1000]}")
        else:
            if n == "vitals.csv":
                ctx.append("## vitals.csv\nBP: 120/78 mmHg, HR: 72 bpm, Temp: 98.7°F, SpO2: 99%, Resp: 16/min")
            elif n == "labs.csv":
                ctx.append("## labs.csv\nCBC: Normal, Glucose: 104 mg/dL, Cholesterol: 182 mg/dL, Hemoglobin: 13.6 g/dL")
            elif n == "imaging.csv":
                ctx.append("## imaging.csv\nChest X-ray: Clear lungs, MRI Brain: Normal, CT Abdomen: No acute findings.")

    ctx.append(summarize_hospitals_and_departments(pid))
    ctx.append(analyze_trends(pid))
    context = "\n".join(ctx)

    system_prompt = (
        "You are a clinical AI assistant. Summarize patient information from vitals, labs, and imaging. "
        "Provide structured insights in sections like Vitals, Labs, Imaging, and Summary. "
        "If data is simulated, mention that it's for demonstration only."
    )

    answer = ask_bedrock(system_prompt, f"Context:\n{context}\n\nQuestion: {q}")
    return {"statusCode": 200, "headers": {}, "body": json.dumps({"answer": answer})}

def handle_generate_pdf(event):
    body = json.loads(event.get("body", "{}")) if event.get("body") else {}
    pid   = body.get("patientId", "unknown")
    pname = body.get("patientName", "Unknown Patient")
    otype = body.get("orderType", "Lab Panel")
    odet  = body.get("orderDetails", "CBC, CMP, Lipid Panel")
    reqby = body.get("requestedBy", "Provider")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, clean_text("Provider Order Summary"), ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, clean_text(f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z"), ln=True)
    pdf.cell(0, 8, clean_text(f"Requested By: {reqby}"), ln=True)
    pdf.ln(5)
    pdf.cell(0, 8, clean_text(f"Patient: {pname} (ID: {pid})"), ln=True)
    pdf.multi_cell(0, 8, clean_text(f"Order Type: {otype}\nDetails: {odet}"))
    pdf.ln(8)
    pdf.multi_cell(0, 8, clean_text("This order is securely generated by I AI Healthcare Connector."))

    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    encoded = base64.b64encode(pdf_bytes).decode("utf-8")
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/pdf",
            "Content-Disposition": f'attachment; filename="{pid}_order.pdf"'
        },
        "isBase64Encoded": True,
        "body": encoded
    }

# ---- ROUTER ----
def lambda_handler(event, context):
    print("Received event:", json.dumps(event, indent=2))
    http_info = event.get("requestContext", {}).get("http", {})
    method = http_info.get("method", event.get("httpMethod", "GET"))
    path = event.get("rawPath") or http_info.get("path") or "/"

    # Handle preflight requests
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": {}, "body": ""}

    if method == "GET" and path in ["/", "/patients"]:
        return handle_list_patients()
    if method == "POST" and path == "/ask":
        return handle_ask(event)
    if method == "POST" and path in ["/order-pdf", "/orderpdf"]:
        return handle_generate_pdf(event)

    return {"statusCode": 404, "headers": {}, "body": json.dumps({"error": f"Not found {method} {path}"})}
