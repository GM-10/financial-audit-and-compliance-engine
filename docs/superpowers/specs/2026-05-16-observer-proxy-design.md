# Observer Proxy Integration Design

## Overview
This design implements an "Observer Proxy" to provide visual debugging and tracing for the existing `deepagents` financial audit system using the Google ADK (Agent Development Kit). This approach enables ADK's visualization UI without requiring a full rewrite of the existing agent logic.

## Architecture
We will implement an observability layer that sits alongside the `deepagents` execution loop.

- **TelemetryHook:** A utility module that intercepts agent tool calls and state transitions.
- **ADK Trace Integration:** Telemetry data will be formatted as ADK trace events and sent to a local ADK tracing server.

## Components
1. **TelemetryHook (`src/telemetry.py`):**
   - Intercepts input/output from the `AuditAgent`.
   - Formats events according to ADK tracing standards.
2. **Proxy Layer:**
   - Wraps the existing `audit_agent.build_agent` logic to enable event capture.

## Data Flow
1. User triggers `main.py`.
2. Execution proceeds via existing `deepagents` workflow.
3. Telemetry hooks capture state snapshots (Input Prompt, Tool Call, Tool Result, Final Output).
4. Captured data is exported to the local ADK visualizer.

## Risks & Mitigations
- **Performance:** Tracing adds minimal overhead. To mitigate, tracing can be toggled via environment variable.
- **Complexity:** Keeping the proxy separate minimizes impact on existing test suite (`pytest`).

## User Review
Please review this design. If it meets your requirements, I will proceed to create an implementation plan using the `writing-plans` skill.
