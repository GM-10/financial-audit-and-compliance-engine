import pandas as pd
from sqlmodel import Session, select
from app.backend.database import engine, AuditReport
import os

def export_approved_reports(session: Session, output_path: str = "audit_settlement_sheet.xlsx"):
    """
    Extracts all APPROVED reports from the database and exports them to a professional
    Excel settlement sheet.
    """
    # Fetch only approved reports
    statement = select(AuditReport).where(AuditReport.status == "APPROVED")
    reports = session.exec(statement).all()

    if not reports:
        return False, "No approved reports found to export."

    # Prepare data for DataFrame
    data = []
    for r in reports:
        data.append({
            "Vendor Name": r.vendor_name,
            "Vendor ID": r.vendor_id,
            "Invoice Amount (INR)": r.invoice_amount,
            "Days Late": r.days_late,
            "Penalty Amount (INR)": r.penalty_amount,
            "Action Required": r.action_required,
            "Auditor Note": r.agent_reasoning
        })

    df = pd.DataFrame(data)

    try:
        # Use an ExcelWriter to allow for better formatting
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Settlement Sheet', index=False)

            # Access the xlsxwriter workbook and worksheet for formatting
            workbook = writer.book
            worksheet = writer.sheets['Settlement Sheet']

            # Add a professional header
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4F81BD',
                'font_color': 'white',
                'border': 1
            })

            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Adjust column widths
            worksheet.set_column('A:A', 25) # Vendor Name
            worksheet.set_column('B:B', 15) # Vendor ID
            worksheet.set_column('G:G', 40) # Auditor Note

        return True, f"Successfully exported to {output_path}"
    except Exception as e:
        return False, f"Export failed: {str(e)}"
