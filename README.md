# I AI Healthcare Connector

## AWS Bedrock + Lambda + S3 + Amplify Prototype for Cross-Hospital AI Data Summarization

###  Inspiration
Working in a hospital, I’ve seen how frustrating it can be when hospitals using the same EMR (like Epic Systems) still rely on fax machines to share patient orders and results. Faxes meet HIPAA standards, but they’re inefficient, delayed, and often lost — leaving both patients and staff asking:

> “We don’t have your order — do you have a paper copy?”

Patients also struggle to manage multiple MyChart logins across hospitals. Even with Epic’s “Care Everywhere,” sharing feels fragmented.

**I AI (Integrated Intelligence)** was born from that challenge — a prototype exploring what if hospitals could securely connect and summarize cross-organizational data automatically?

---

###  About the Prototype
**I AI** is a cloud-based agentic AI system designed to simulate intelligent healthcare data summarization using:

- **Amazon Bedrock (Claude 3.5 Sonnet)** for reasoning and summarization  
- **AWS Lambda** for backend processing  
- **Amazon S3** for patient data storage (synthetic, via Synthea)  
- **AWS Amplify** for the web-based user interface  
- **FPDF** for generating downloadable care summary reports  

This prototype demonstrates a “what-if” scenario — showing how AI could unify fragmented patient data, summarize encounters, and generate care summaries to reduce manual review, faxing, and paperwork.

---

##  Technical Architecture

<img width="1231" height="733" alt="Screenshot (663)" src="https://github.com/user-attachments/assets/b34ca7a2-a2e0-46a1-b714-4d2d428aa2b4" />


**Figure 1. I AI Healthcare Connector — AWS Architecture Overview**

1. **Patients/Clinicians** interact through the **AWS Amplify** web app.  
2. **Amplify** sends requests to **AWS Lambda**, which processes and routes data.  
3. **S3** stores synthetic patient data (generated via Synthea).  
4. **AWS Lambda** interacts with **Amazon Bedrock** for AI-powered summaries and order verification.  
5. **FPDF** generates downloadable care summary PDFs.  
6. **IAM Roles**, **CloudTrail**, and **CloudWatch** ensure security, logging, and monitoring.

---

##  Technologies Used
| Category | Tools / Services |
|-----------|------------------|
| **Languages** | Python, HTML, JavaScript |
| **Cloud Services** | AWS Bedrock, AWS Lambda, S3, Amplify |
| **Frameworks** | FPDF (PDF generation), Pandas |
| **AI Model** | Anthropic Claude 3.5 Sonnet (via Amazon Bedrock) |
| **APIs** | S3 File API, Lambda REST Endpoints |
| **Dataset** | Synthetic EMR data (Synthea-generated) |

---
###  How It Works

1. **Synthetic Patient Data** is stored in an S3 bucket (JSON/CSV format).  
2. The **Amplify frontend** allows users to:  
   - Ask general health questions  
   - Select a patient for AI-based summaries  
   - Clear chat or download a PDF report  
3. **Lambda backend** fetches data from S3 and sends context to **Amazon Bedrock (Claude 3.5 Sonnet)** for reasoning.  
4. **FPDF** generates prototype PDF summaries on demand.

---

###  Key Features

- Dual-mode AI (General Q&A + Patient-Specific Insights)  
- Bedrock reasoning and summarization through Lambda  
- Real-time data retrieval from S3  
- Responsive Amplify web interface (mobile-friendly)  
- Prototype PDF report generation  
- Secure architecture using IAM, CloudTrail, and CloudWatch  

---

###  Architecture Overview

1. Users interact through the **Amplify web app**
2. Amplify sends requests to **AWS Lambda**, which processes them
3. **S3** stores synthetic patient data (Synthea-generated)
4. Lambda sends context to **Amazon Bedrock** for reasoning and summarization
5. **FPDF** generates downloadable care summaries
6. **IAM**, **CloudTrail**, and **CloudWatch** ensure monitoring and security

---

### Technologies Used

| Category | Tools & Services |
|-----------|------------------|
| **Languages** | Python, HTML, JavaScript |
| **Cloud Services** | AWS Bedrock, AWS Lambda, Amazon S3, AWS Amplify |
| **Frameworks/Libraries** | FPDF (PDF generation), Pandas |
| **AI Model** | Claude 3.5 Sonnet (via Amazon Bedrock) |
| **Dataset** | Synthetic EMR data (Synthea) |

---

###  Accomplishments

- Built a working AI + Cloud integration using AWS Bedrock and Lambda  
- Successfully deployed on AWS Amplify with real-time Bedrock responses  
- Implemented a dual-mode AI flow (general vs. patient-aware)  
- Managed CORS and cross-service permissions successfully  
- Designed an intuitive UI for both desktop and mobile  

---

###  Challenges

- Configuring CORS and Lambda permissions for cross-service access  
- Managing large JSON/FHIR data while keeping Lambda layer under AWS limits  
- Simplifying the user flow between multiple AWS services  

---

###  What We Learned

- How to orchestrate multi-service AI pipelines in AWS  
- Best practices for managing serverless AI agents and cost optimization  
- Importance of UI clarity when demonstrating cloud-based AI prototypes  

---

###  What’s Next

- Integrate with FHIR APIs for real hospital interoperability  
- Enable Bedrock Agents with memory and reasoning primitives  
- Add multi-agent collaboration (provider and patient roles)  
- Extend support to Amazon Q and SageMaker endpoints  
- Prototype Epic + Bedrock data summarization model  

---

##  Links
- **Deployed App:** [Amplify Demo Link](https://staging.d182bt6nvemywj.amplifyapp.com/)    
- **Video Demo:** [YouTube Demo Link (to be added)]  
- **Devpost Submission:** [I AI Healthcare Connector on Devpost](https://devpost.com/...)  

---

© 2025 Tinsae Tesfaye — AWS AI Agent Global Hackathon Project
