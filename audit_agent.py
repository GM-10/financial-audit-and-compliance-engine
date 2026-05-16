from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from deepagents import create_deep_agent
from loguru import logger
from src.telemetry import trace_event
from src.web_tools import fetch_contract_from_portal
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
DEFAULT_MODEL = "openrouter:inclusionai/ring-2.6-1t:free"

CONTRACTS_DIR = ROOT / "contracts"
DB_PATH = ROOT / "ap_ledger.db"
DELIVERY_LOG_PATH = ROOT / "warehouse_receipts_fy26.csv"
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

Your final report must reflect the exact calculations derived from the contract text.
""".strip()

def _connect():
    import sqlite3
    return sqlite3.connect(DB_PATH)

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

def check_delivery_log(vendor_id: str) -> str:
    """Return warehouse receipt rows for a vendor without exposing unrelated rows."""
    import pandas as pd
    frame = pd.read_csv(DELIVERY_LOG_PATH)
    rows = frame.loc[frame["Vendor_ID"] == vendor_id].copy()
    rows["days_late"] = (
        pd.to_datetime(rows["Actual_Delivery"]) - pd.to_datetime(rows["Expected_Delivery"])
    ).dt.days
    return rows.to_json(orient="records")

def read_contract(vendor_name: str) -> str:
    # Try different extensions: .txt, .pdf, .docx
    for ext in [".txt", ".pdf", ".docx"]:
        filename = vendor_name.replace(" ", "_") + ext
        path = CONTRACTS_DIR / filename
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

    existing_files = [f.name for f in CONTRACTS_DIR.iterdir()]
    raise FileNotFoundError(f"No contract found for {vendor_name} (.txt, .pdf, or .docx) at {CONTRACTS_DIR}. Existing files: {existing_files}")

def read_file(vendor_name: str) -> str:
    """Read a contract file (PDF, DOCX, or TXT) for a vendor by name."""
    try:
        return read_contract(vendor_name)
    except FileNotFoundError:
        return f"Contract not found for vendor: {vendor_name}. Available contracts are in {CONTRACTS_DIR}"

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
        load_dotenv(ENV_PATH)
        return os.getenv("OPENROUTER_MODEL") or os.getenv("MODEL_NAME") or DEFAULT_MODEL

    def _build_agent(self):
        return create_deep_agent(
            model=self.model_name,
            tools=[query_ledger, check_delivery_log, read_file, fetch_contract_from_portal],
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

        vendor_id = get_vendor_id(vendor_name)
        invoices = query_ledger(
            "select Invoice_ID, Vendor_ID, Amount, Invoice_Date, Status "
            f"from Invoices where Vendor_ID = '{vendor_id}'"
        )
        deliveries = check_delivery_log(vendor_id)
        contract_text = read_contract(vendor_name)
        return (
            f"{prompt}\n\n"
            "LOCAL REFERENCE DATA\n"
            f"Vendor: {vendor_name}\n"
            f"Vendor ID: {vendor_id}\n"
            f"DB Schema Hint: {LEDGER_SCHEMA_HINT} "
            "Use Vendors.Vendor_ID to join Vendors and Invoices, then Payments.Invoice_ID to join Payments; there is no accounts_payable table.\n"
            "Tool Guidance: query_ledger accepts read-only SELECT SQL. "
            f"Use check_delivery_log(\"{vendor_id}\") for warehouse receipts and read_file(\"{vendor_name}\") for the contract.\n"
            "Response Shape: return a DiscrepancyReport with vendor_id, vendor_name, invoice_amount, "
            "days_late, penalty_amount_inr, and action_required.\n\n"
            "Known-good SQL examples:\n"
            f"- select Vendor_ID, Vendor_Name from Vendors where Vendor_Name = '{vendor_name}'\n"
            f"- select Invoice_ID, Vendor_ID, Amount, Invoice_Date, Status from Invoices where Vendor_ID = '{vendor_id}'\n"
            f"- select Payment_ID, Invoice_ID, Amount, Payment_Date from Payments where Invoice_ID = 'INV-2000'\n\n"
            "Contract:\n"
            f"{contract_text}\n\n"
            "Invoice Rows:\n"
            f"{invoices}\n\n"
            "Delivery Rows:\n"
            f"{deliveries}\n"
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
            reasoning_chain = "\\n".join([
                f"{m.get('role', 'unknown')}: {m.get('content', '')}"
                for m in messages[:-1]
            ])

        if not messages:
            return "No response from agent.", ""

        final = messages[-1]
        content = str(getattr(final, "content", final))

        if isinstance(content, DiscrepancyReport):
            trace_event("audit_complete", {"report": content.model_dump()})
            return content, reasoning_chain

        try:
            if hasattr(final, 'content') and isinstance(final.content, DiscrepancyReport):
                report = final.content
                trace_event("audit_complete", {"report": report.model_dump()})
                return report, reasoning_chain
            return content, reasoning_chain
        except Exception:
            return content, reasoning_chain

def run_self_check() -> str:
    service = AuditAgentService()
    report = service.invoke("Audit Gujarat Steel Corp")
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
    print(service.invoke(args.prompt))
    return 0
