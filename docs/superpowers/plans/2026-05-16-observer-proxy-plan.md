# Observer Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the Google ADK-Python tracing and visualization layer into the existing `deepagents` project to enable visual agent debugging via an "Observer Proxy".

**Architecture:** We will create a `telemetry.py` to capture agent state and wrap the `build_agent` logic to emit ADK-compatible trace events.

**Tech Stack:** `google-adk`, `deepagents`.

---

### Task 1: Initialize ADK environment and telemetry module

**Files:**
- Create: `src/telemetry.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dependency to `pyproject.toml`**

```toml
dependencies = [
    ...
    "google-adk>=0.1.0",
]
```

- [ ] **Step 2: Create `src/telemetry.py`**

```python
from google.adk.tracing import tracer
from typing import Any

def trace_event(event_name: str, payload: Any):
    """Bridge for emitting ADK traces."""
    tracer.emit(event_name, payload)
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml src/telemetry.py
git commit -m "feat: add ADK tracing dependency and telemetry module"
```

### Task 2: Implement Observer Proxy for Audit Agent

**Files:**
- Modify: `audit_agent.py`

- [ ] **Step 1: Import telemetry in `audit_agent.py`**

```python
from src.telemetry import trace_event
```

- [ ] **Step 2: Wrap agent invocation to emit traces**

Modify `invoke_agent` in `audit_agent.py`:

```python
def invoke_agent(prompt: str) -> str:
    agent = build_agent(load_model_name())
    trace_event("agent_input", {"prompt": prompt})
    result = agent.invoke({"messages": [{"role": "user", "content": build_augmented_prompt(prompt)}]})
    trace_event("agent_output", {"result": result})
    messages = result.get("messages", [])
    if not messages:
        return ""
    final = messages[-1]
    return str(getattr(final, "content", final))
```

- [ ] **Step 3: Commit**

```bash
git add audit_agent.py
git commit -m "feat: integrate ADK observer proxy into audit agent"
```

### Task 3: Verification

**Files:**
- Test: `tests/test_chapter_06.py`

- [ ] **Step 1: Add a test to verify telemetry flow**

Add to `tests/test_chapter_06.py`:

```python
def test_telemetry_proxy_is_active(monkeypatch):
    calls = []
    def mock_emit(name, payload):
        calls.append((name, payload))
    
    monkeypatch.setattr("src.telemetry.tracer.emit", mock_emit)
    audit_agent.invoke_agent("Audit the account for Gujarat Steel Corp.")
    
    assert any(c[0] == "agent_input" for c in calls)
    assert any(c[0] == "agent_output" for c in calls)
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest`

- [ ] **Step 3: Commit**

```bash
git add tests/test_chapter_06.py
git commit -m "test: add telemetry verification"
```
