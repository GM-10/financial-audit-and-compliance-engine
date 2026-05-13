import json
from pydantic import ValidationError
import audit_agent


def test_discrepancy_report_schema_accepts_expected_fields():
    report = audit_agent.build_discrepancy_report("Gujarat Steel Corp")
    assert report.vendor_id == "VEN-1000"
    assert report.penalty_amount_inr == 25000.0
    assert report.action_required == "Recover Funds"


def test_printable_report_is_valid_json():
    payload = json.loads(audit_agent.report_to_json(audit_agent.build_discrepancy_report("Gujarat Steel Corp")))
    assert payload["vendor_name"] == "Gujarat Steel Corp"
    assert payload["days_late"] == 14


def test_schema_rejects_missing_required_fields():
    try:
        audit_agent.DiscrepancyReport(vendor_id="VEN-1000")
    except ValidationError:
        return
    raise AssertionError("schema accepted an incomplete report")
