from google.adk.tracing import tracer
from typing import Any

def trace_event(event_name: str, payload: Any):
    """Bridge for emitting ADK traces."""
    tracer.emit(event_name, payload)
