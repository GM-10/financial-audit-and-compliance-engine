from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

from .config import settings
from deepagents import create_deep_agent
from loguru import logger
from .telemetry import trace_event, trace_tool
from .web_tools import fetch_contract_from_portal
from pydantic import BaseModel, Field

# Configuration provided by settings module
LEDGER_SCHEMA_HINT = (
    "Tables: Vendors, Invoices, Payments. Columns: Vendors(Vendor_ID, Vendor_Name, GSTIN, Address), "
    "Invoices(Invoice_ID, Vendor_ID, Amount, Invoice_Date, Status), "
    "Payments(Payment_ID, Invoice_ID, Amount, Payment_Date). "
    "Payments uses Amount for the payment amount; there is no Payment_Amount column."
)

SYSTEM_PROMPT = """
You are the Senior Financial Auditor for Shree Manufacturing Pvt. Ltd.
You MUST use write_todos to outline a 3-step audit plan before taking any other action.
Use query_ledger for accounts payable data, check_delivery_log for warehouse receipts, and read_file for legal contracts.

PENALTY CALCULATION RULES:
1. Locate the specific "Late Delivery" or "Penalty" clause in the vendor's contract.
2. Determine the exact penalty rate (e.g., percentage per day, fixed flat fee, or tiered rates).
3. Apply the rate to the invoice amount based on the number of days late identified in the delivery log.
4. If no penalty clause exists or conditions are not met, penalty_amount_inr should be 0.0.

WORKFLOW AUTOMATION:
If a penalty_amount_inr > 0 is found, you MUST use send_gmail_notification EXACTLY ONCE to email the vendor about the discrepancy. The purpose of this email is to immediately notify them and initiate the penalty recovery process. Once the notification tool has been called, immediately proceed to return your final report.

Your final report must reflect the exact calculations derived from the contract text.
""".strip()

def _connect():
    import sqlite3
    return sqlite3.connect(settings.DB_PATH)

@trace_tool
def query_ledger(sql: str) -> str:
    """Execute a read-only SQL query against the accounts payable ledger."""
    lowered = sql.strip().lower()
    if not lowered.startswith("select"):
        raise ValueError("Only SELECT statements are allowed")
    with _connect() as con:
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(sql).fetchall()
        except sqlite3.Error as exc:
            return json.dumps(
                {
                    "error": "Invalid SELECT for this ledger schema",
                    "message": str(exc),
                    "schema_hint": LEDGER_SCHEMA_HINT,
                }
            )
    return json.dumps([dict(row) for row in rows])

@trace_tool
def check_delivery_log(vendor_id: str) -> str:
    """Return warehouse receipt rows for a vendor without exposing unrelated rows."""
    import pandas as pd
    frame = pd.read_csv(settings.DELIVERY_LOG_PATH)
    rows = frame.loc[frame["Vendor_ID"] == vendor_id].copy()
    rows["days_late"] = (
        pd.to_datetime(rows["Actual_Delivery"]) - pd.to_datetime(rows["Expected_Delivery"])
    ).dt.days
    return rows.to_json(orient="records")

def read_contract(vendor_name: str) -> str:
    # Try different extensions: .txt, .pdf, .docx
    for ext in [".txt", ".pdf", ".docx"]:
        # Try both base name and name with "_Contract" suffix
        base_name = vendor_name.replace(" ", "_")
        for name in [f"{base_name}{ext}", f"{base_name}_Contract{ext}"]:
            path = settings.CONTRACTS_DIR / name
            if path.exists():
                if ext == ".txt":
                    return path.read_text(encoding="utf-8")
                elif ext == ".pdf":
                    try:
                        from pypdf import PdfReader
                        reader = PdfReader(path)
                        return "\\n".join([page.extract_text() for page in reader.pages])
                    except ImportError:
                        return f"[Error: pypdf not installed. Cannot read PDF {path.name}]"
                elif ext == ".docx":
                    try:
                        import docx
                        doc = docx.Document(path)
                        return "\\n".join([p.text for p in doc.paragraphs])
                    except ImportError:
                        return f"[Error: python-docx not installed. Cannot read DOCX {path.name}]"

    # Fallback: Search for any file that contains the vendor name
    for file in settings.CONTRACTS_DIR.iterdir():
        if vendor_name.replace(" ", "_") in file.name:
            if file.suffix == ".txt":
                return file.read_text(encoding="utf-8")
            # (Could add pdf/docx support here too)

    existing_files = [f.name for f in settings.CONTRACTS_DIR.iterdir()]
    raise FileNotFoundError(f"No contract found for {vendor_name} (.txt, .pdf, or .docx) at {settings.CONTRACTS_DIR}. Existing files: {existing_files}")

@trace_tool
def read_file(vendor_name: str) -> str:
    """Read a contract file (PDF, DOCX, or TXT) for a vendor by name."""
    try:
        return read_contract(vendor_name)
    except FileNotFoundError:
        return f"Contract not found for vendor: {vendor_name}. Available contracts are in {settings.CONTRACTS_DIR}"

@trace_tool
def send_gmail_notification(to_email: str, subject: str, body: str) -> str:
    """Send an email notification to a vendor via Gmail. Use this to notify vendors of penalties."""
    gmail_user = settings.gmail_user
    gmail_pass = settings.gmail_app_password

    if not gmail_user or not gmail_pass:
        # If credentials aren't set, simulate the email for workshop demonstration
        logger.warning(f"Gmail credentials missing. Simulated Email to {to_email}: {subject}")
        return f"Simulated sending email to {to_email}. Ensure GMAIL_USER and GMAIL_APP_PASSWORD are in .env for real emails."

    try:
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_pass)
        text = msg.as_string()
        server.sendmail(gmail_user, to_email, text)
        server.quit()
        return f"Successfully sent real email notification to {to_email}"
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return f"Error sending email: {str(e)}"

def get_vendor_id(vendor_name: str) -> str:
    rows = json.loads(query_ledger(f"select Vendor_ID from Vendors where Vendor_Name = '{vendor_name}'"))
    if not rows:
        raise ValueError(f"Unknown vendor: {vendor_name}")
    return rows[0]["Vendor_ID"]

class DiscrepancyReport(BaseModel):
    vendor_id: str = Field(description="The unique ID of the vendor")
    vendor_name: str
    invoice_amount: float
    days_late: int
    penalty_amount_inr: float
    action_required: str = Field(description="e.g., 'Recover Funds', 'None'")

class AuditAgentService:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or self._load_model_name()
        self.agent = self._build_agent()

    def _load_model_name(self) -> str:
        model = settings.openrouter_model
        if model.startswith("openrouter:"):
            return model[len("openrouter:"):]
        return model

    def _build_agent(self):
        from langchain_openrouter import ChatOpenRouter
        
        # Instantiate model with lower max_tokens to avoid OpenRouter credit check failures
        llm = ChatOpenRouter(
            model=self.model_name,
            max_tokens=4000
        )
        
        return create_deep_agent(
            model=llm,
            tools=[query_ledger, check_delivery_log, read_file, fetch_contract_from_portal, send_gmail_notification],
            system_prompt=SYSTEM_PROMPT,
            response_format=DiscrepancyReport,
        )

    def _normalize(self, text: str) -> str:
        return " ".join(text.lower().split())

    def _known_vendor_names(self) -> list[str]:
        rows = json.loads(query_ledger("select Vendor_Name from Vendors"))
        return sorted((row["Vendor_Name"] for row in rows), key=len, reverse=True)

    def _find_vendor_in_prompt(self, prompt: str) -> str | None:
        normalized_prompt = self._normalize(prompt)
        for vendor_name in self._known_vendor_names():
            if self._normalize(vendor_name) in normalized_prompt:
                return vendor_name
        return None

    def build_augmented_prompt(self, prompt: str) -> str:
        vendor_name = self._find_vendor_in_prompt(prompt)
        if vendor_name is None:
            return prompt

        try:
            vendor_id = get_vendor_id(vendor_name)
        except ValueError:
            return prompt

        contract_text = read_contract(vendor_name)
        
        return (
            f"{prompt}\n\n"
            "CONTEXTUAL GUIDANCE\n"
            f"Target Vendor: {vendor_name} (ID: {vendor_id})\n"
            "To complete this audit, you should:\n"
            f"1. Fetch invoices for Vendor ID {vendor_id} using query_ledger.\n"
            f"2. Check delivery logs for Vendor ID {vendor_id} using check_delivery_log.\n"
            f"3. Review the contract details provided below for penalty clauses.\n\n"
            "DB Schema Hint: Tables: Vendors, Invoices, Payments. Columns: Vendors(Vendor_ID, Vendor_Name, GSTIN, Address), Invoices(Invoice_ID, Vendor_ID, Amount, Invoice_Date, Status), Payments(Payment_ID, Invoice_ID, Amount, Payment_Date).\n\n"
            "CONTRACT TEXT:\n"
            f"{contract_text}\n"
        )

    def invoke(self, prompt: str) -> tuple[DiscrepancyReport | str, str]:
        augmented_prompt = self.build_augmented_prompt(prompt)

        # Telemetry trace for audit start
        trace_event("audit_start", {"prompt": prompt, "augmented_prompt": augmented_prompt})

        result = self.agent.invoke({"messages": [{"role": "user", "content": augmented_prompt}]})

        messages = result.get("messages", [])

        # Capture the reasoning chain (all messages except the final structured response)
        reasoning_chain = ""
        if messages:
            chain_parts = []
            for m in messages[:-1]:
                if isinstance(m, dict):
                    role = m.get("role", m.get("type", "unknown"))
                    content = m.get("content", "")
                else:
                    role = getattr(m, "type", getattr(m, "role", "unknown"))
                    content = getattr(m, "content", "")
                chain_parts.append(f"{role}: {content}")
            reasoning_chain = "\\n".join(chain_parts)
            trace_event("agent_reasoning", {"chain": reasoning_chain})

        if not messages:
            return "No response from agent.", ""

        final = messages[-1]
        content = getattr(final, "content", final)

        if isinstance(content, DiscrepancyReport):
            trace_event("audit_complete", {"report": content.model_dump()})
            return content, reasoning_chain

        return str(content), reasoning_chain

def run_self_check() -> str:
    service = AuditAgentService()
    report, _ = service.invoke("Audit Gujarat Steel Corp")
    if isinstance(report, DiscrepancyReport):
        return report.model_dump_json(indent=2)
    return str(report)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="?", default="What is your job?")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)

    if args.self_check:
        print(run_self_check())
        return 0

    service = AuditAgentService()
    report, reasoning = service.invoke(args.prompt)
    print(f"REPORT:\n{report}")
    if reasoning:
        print(f"\nREASONING:\n{reasoning}")
    return 0
