from src.auditor.agent import AuditAgentService
import os

def test():
    print("Starting agent...")
    try:
        service = AuditAgentService()
        print("Agent initialized. Invoking...")
        result = service.invoke("Audit Gujarat Steel Corp")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
