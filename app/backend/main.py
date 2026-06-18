from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel

# Handle imports from the root directory
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.auditor.agent import AuditAgentService, DiscrepancyReport
from app.backend.database import engine, create_db_and_tables, get_session, AuditReport
from app.backend.export_service import export_approved_reports

app = FastAPI(title="AI Financial Auditor API")

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB
@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# Services
agent_service = AuditAgentService()

class ReportUpdate(BaseModel):
    status: str # APPROVED, REJECTED
    note: Optional[str] = None

@app.post("/audit/{vendor_name}")
async def trigger_audit(vendor_name: str, session: Session = Depends(get_session)):
    try:
        # The agent service takes a prompt. We'll pass a structured request for the vendor.
        prompt = f"Perform a full audit for vendor: {vendor_name}. Calculate penalties based on delivery logs and contracts."
        report, reasoning = agent_service.invoke(prompt)

        if isinstance(report, str):
            raise HTTPException(status_code=500, detail=f"Agent failed to produce structured report: {report}")

        # Store in DB
        db_report = AuditReport(
            vendor_id=report.vendor_id,
            vendor_name=report.vendor_name,
            invoice_amount=report.invoice_amount,
            penalty_amount=report.penalty_amount_inr,
            days_late=report.days_late,
            status="PENDING",
            action_required=report.action_required,
            agent_reasoning=reasoning
        )
        session.add(db_report)
        session.commit()
        session.refresh(db_report)

        return db_report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports", response_model=List[AuditReport])
async def list_reports(session: Session = Depends(get_session)):
    reports = session.exec(select(AuditReport)).all()
    return reports

@app.patch("/reports/{report_id}")
async def update_report_status(report_id: int, update: ReportUpdate, session: Session = Depends(get_session)):
    report = session.get(AuditReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if update.status not in ["APPROVED", "REJECTED"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be APPROVED or REJECTED")

    report.status = update.status
    if update.note:
        report.agent_reasoning = f"{report.agent_reasoning}\nHuman Note: {update.note}"

    session.add(report)
    session.commit()
    session.refresh(report)
    return report

@app.get("/export/settlement")
async def export_settlement_sheet(session: Session = Depends(get_session)):
    success, message = export_approved_reports(session)
    if not success:
        raise HTTPException(status_code=500, detail=message)

    return FileResponse(
        path="audit_settlement_sheet.xlsx",
        filename="Audit_Settlement_Sheet.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
