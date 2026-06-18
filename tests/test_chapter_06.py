import json
from pydantic import ValidationError
from src.auditor.agent import DiscrepancyReport, AuditAgentService
import src.auditor.agent as audit_agent

def test_discrepancy_report_schema_accepts_expected_fields():
    # Helper to calculate report independently
    report = DiscrepancyReport(
        vendor_id="VEN-1000",
        vendor_name="Gujarat Steel Corp",
        invoice_amount=500000.0,
        days_late=14,
        penalty_amount_inr=25000.0,
        action_required="Recover Funds"
    )
    assert report.vendor_id == "VEN-1000"
    assert report.penalty_amount_inr == 25000.0
    assert report.action_required == "Recover Funds"


def test_printable_report_is_valid_json():
    # Helper to calculate report independently
    report = DiscrepancyReport(
        vendor_id="VEN-1000",
        vendor_name="Gujarat Steel Corp",
        invoice_amount=500000.0,
        days_late=14,
        penalty_amount_inr=25000.0,
        action_required="Recover Funds"
    )
    payload = json.loads(report.model_dump_json())
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
    service = AuditAgentService()
    prompt = service.build_augmented_prompt("Audit the account for Gujarat Steel Corp.")

    assert "Gujarat Steel Corp" in prompt
    assert "VEN-1000" in prompt
    assert "INV-2000" in prompt
    assert "DiscrepancyReport" in prompt
    assert "vendor_id" in prompt
    assert "penalty_amount_inr" in prompt
    assert "check_delivery_log(\"VEN-1000\")" in prompt


def test_telemetry_proxy_is_active(monkeypatch):
    calls = []

    def mock_trace_event(event_name, payload):
        calls.append((event_name, payload))

    monkeypatch.setattr("src.auditor.agent.trace_event", mock_trace_event)
    
    # Mock agent invoke to avoid LLM network call in unit test
    class MockAgent:
        def invoke(self, messages):
            report = DiscrepancyReport(
                vendor_id="VEN-1000",
                vendor_name="Gujarat Steel Corp",
                invoice_amount=500000.0,
                days_late=14,
                penalty_amount_inr=25000.0,
                action_required="Recover Funds"
            )
            # Create a mock response object that has a 'content' attribute matching final output expectation
            class MockResponse:
                def __init__(self, content):
                    self.content = content
            return {"messages": [{"role": "user", "content": "dummy"}, MockResponse(report)]}
            
    service = AuditAgentService()
    service.agent = MockAgent()
    service.invoke("Audit the account for Gujarat Steel Corp.")

    assert any(c[0] == "audit_start" for c in calls)
    assert any(c[0] == "audit_complete" for c in calls)
