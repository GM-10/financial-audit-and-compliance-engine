from typing import Optional
from sqlmodel import Field, SQLModel, create_engine, Session, select
import os

# Configuration
DB_FILE = os.getenv("DATABASE_URL", "audit_reports.db")
sqlite_url = f"sqlite:///{DB_FILE}"
engine = create_engine(sqlite_url, echo=True)

class AuditReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    vendor_id: str
    vendor_name: str
    invoice_amount: float
    penalty_amount: float
    days_late: int
    status: str = Field(default="PENDING")  # PENDING, APPROVED, REJECTED
    agent_reasoning: Optional[str] = None
    action_required: str
    created_at: Optional[float] = None # Simplified timestamp

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
