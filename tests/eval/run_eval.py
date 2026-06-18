import json
import sys
from pathlib import Path
from src.auditor.agent import AuditAgentService, DiscrepancyReport

def run_evaluation():
    # Use absolute path to avoid CWD issues
    ROOT = Path(__file__).resolve().parent.parent.parent
    GOLD_PATH = ROOT / "tests/eval/gold_dataset.json"

    if not GOLD_PATH.exists():
        print(f"Error: Gold dataset not found at {GOLD_PATH}")
        return

    with open(GOLD_PATH, "r") as f:
        test_cases = json.load(f)

    service = AuditAgentService()
    results = []
    correct = 0

    print(f"Starting evaluation on {len(test_cases)} cases...\n")
    print(f"{'Vendor':<25} | {'Expected':<10} | {'Actual':<10} | {'Status'}")
    print("-" * 60)

    for case in test_cases:
        vendor = case["vendor_name"]
        expected = case["expected_penalty"]

        try:
            report, reasoning = service.invoke(f"Perform a full audit for vendor: {vendor}. Calculate penalties based on delivery logs and contracts.")

            if isinstance(report, DiscrepancyReport):
                actual = report.penalty_amount_inr
            else:
                actual = None

            is_correct = (actual == expected) if actual is not None else False
            if is_correct:
                correct += 1

            status = "✅" if is_correct else "❌"
            print(f"{vendor:<25} | {expected:<10.2f} | {str(actual):<10} | {status}")

            results.append({
                "vendor": vendor,
                "expected": expected,
                "actual": actual,
                "status": "PASS" if is_correct else "FAIL",
                "reasoning": reasoning
            })
        except Exception as e:
            print(f"{vendor:<25} | Error: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append({"vendor": vendor, "expected": expected, "actual": "ERROR", "status": "FAIL", "reasoning": str(e)})

    accuracy = (correct / len(test_cases)) * 100
    print("-" * 60)
    print(f"Final Accuracy: {accuracy:.2f}% ({correct}/{len(test_cases)})")

    # Save report to markdown at root for easy access
    REPORT_PATH = ROOT / "eval_report.md"
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Audit Agent Evaluation Report\n\n")
        f.write(f"**Overall Accuracy: {accuracy:.2f}%**\n\n")
        f.write("| Vendor | Expected | Actual | Status |\n")
        f.write("|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['vendor']} | {r['expected']} | {r['actual']} | {r['status']} |\n")

    print(f"\nDetailed report saved to {REPORT_PATH}")

if __name__ == "__main__":
    run_evaluation()
