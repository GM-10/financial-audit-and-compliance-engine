from google.adk import telemetry
from typing import Any, Callable
from loguru import logger
import functools
import asyncio

def trace_event(event_name: str, payload: Any):
    """Bridge for emitting ADK traces."""
    with telemetry.tracer.start_span(event_name) as span:
        if payload:
            span.set_attribute("payload", str(payload))
        logger.info(f"Trace Event: {event_name} - {payload}")

def trace_tool(func: Callable):
    """Decorator to trace tool calls."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        async def async_wrapper():
            event_name = f"tool_call_{func.__name__}"
            payload = {"args": args, "kwargs": kwargs}
            trace_event(event_name, payload)
            try:
                result = await func(*args, **kwargs)
                trace_event(f"tool_result_{func.__name__}", {"result": result})
                return result
            except Exception as e:
                trace_event(f"tool_error_{func.__name__}", {"error": str(e)})
                raise e

        if asyncio.iscoroutinefunction(func):
            return async_wrapper()
        else:
            event_name = f"tool_call_{func.__name__}"
            payload = {"args": args, "kwargs": kwargs}
            trace_event(event_name, payload)
            try:
                result = func(*args, **kwargs)
                trace_event(f"tool_result_{func.__name__}", {"result": result})
                return result
            except Exception as e:
                trace_event(f"tool_error_{func.__name__}", {"error": str(e)})
                raise e
    return wrapper
