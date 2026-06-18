# Integrated Agent Design: ADK, Browser-Use, & Chrome DevTools

## Overview
This design integrates Google ADK-Python, Browser-Use, and Chrome DevTools MCP into the existing `AuditAgentService` to transform it from a static file-based processor into an interactive, self-correcting web agent capable of live portal interaction.

## Architecture
- **Orchestrator:** Google ADK-Python manages the audit agent lifecycle and provides real-time telemetry tracing.
- **Web Actor:** Browser-Use automates interaction with external vendor portals to fetch contracts/invoices dynamically.
- **Debugger:** Chrome DevTools MCP enables introspection of browser state for self-healing and detailed diagnostics.

## Data Integration Flow
`[Vendor Portal]` -> `[Browser-Use]` -> `[Normalization Layer]` -> `[AuditAgentService]`

The `AuditAgentService` acts as the interface between the dynamic data stream from the web actor and the existing financial audit logic.

## Self-Healing & Debugging
The agent utilizes the Chrome DevTools MCP to perform "Observer & Healer" cycles:
1. Detect interaction failure.
2. Inspect network/console/DOM state via DevTools.
3. Diagnose and adjust strategies (e.g., update selectors or retry logic).

## Conclusion
This integration enables live web interaction and robust, transparent automation.
