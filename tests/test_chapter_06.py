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


def test_query_ledger_returns_schema_guidance_for_malformed_select():
    result = json.loads(audit_agent.query_ledger("select p.Payment_Amount from Payments p"))

    assert result["error"] == "Invalid SELECT for this ledger schema"
    assert "Tables: Vendors, Invoices, Payments" in result["schema_hint"]


def test_schema_rejects_missing_required_fields():
    try:
        audit_agent.DiscrepancyReport(vendor_id="VEN-1000")
    except ValidationError:
        return
    raise AssertionError("schema accepted an incomplete report")


def test_build_augmented_prompt_includes_report_shape_for_known_vendor():
    prompt = audit_agent.build_augmented_prompt("Audit the account for Gujarat Steel Corp.")

    assert "Gujarat Steel Corp" in prompt
    assert "VEN-1000" in prompt
    assert "INV-2000" in prompt
    assert "DiscrepancyReport" in prompt
    assert "vendor_id" in prompt
    assert "penalty_amount_inr" in prompt
    assert "check_delivery_log(\"VEN-1000\")" in prompt


def test_telemetry_proxy_is_active(monkeypatch):
    calls = []

    def mock_emit(name, payload):
        calls.append((name, payload))

    monkeypatch.setattr("src.telemetry.tracer.emit", mock_emit)
    audit_agent.invoke_agent("Audit the account for Gujarat Steel Corp.")

    assert any(c[0] == "agent_input" for c in calls)
    assert any(c[0] == "agent_output" for c in calls)
