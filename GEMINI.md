# Project: pdeu-conf-chapter-06

This project is an automated financial audit system designed to identify discrepancies in accounts payable. It uses an AI agent (Senior Financial Auditor) to cross-reference multiple data sources and generate structured reports.

## Architecture & Data Flow

```text
                    +---------------------------------------+
                    |          User CLI (main.py)           |
                    +-------------------+-------------------+
                                        |
                                        v
                    +-------------------+-------------------+
                    |        Audit Agent Controller         |
                    |           (audit_agent.py)            |
                    +-------------------+-------------------+
                                        |
          +-----------------------------+-----------------------------+
          |                             |                             |
          v                             v                             v
+-------------------+         +-------------------+         +-------------------+
|   query_ledger    |         |check_delivery_log |         |     read_file     |
|      (Tool)       |         |      (Tool)       |         |      (Tool)       |
+---------+---------+         +---------+---------+         +---------+---------+
          |                             |                             |
          v                             v                             v
+---------+---------+         +---------+---------+         +---------+---------+
|   ap_ledger.db    |         | warehouse_receipts|         |    contracts/     |
|  (SQLite Ledger)  |         |   _fy26.csv       |         | (Vendor Policies) |
+-------------------+         +-------------------+         +-------------------+
                                        |
                                        v
                    +---------------------------------------+
                    |      Structured Output Generation     |
                    |         (DiscrepancyReport)           |
                    +---------------------------------------+
```

## Tech Stack

- **Language:** Python 3.12+ (managed by `uv`)
- **Agent Framework:** `deepagents`
- **Data Handling:** `pandas`, `sqlite3`
- **Validation:** `pydantic`
- **Testing:** `pytest`
- **LLM Connectivity:** `langchain-openrouter`

## Key Files

- `audit_agent.py`: Core logic for the audit agent, including tool definitions and prompt augmentation.
- `main.py`: Entry point for the CLI.
- `ap_ledger.db`: SQLite database with `Vendors`, `Invoices`, and `Payments` tables.
- `warehouse_receipts_fy26.csv`: Delivery log for late-delivery penalty calculations.
- `contracts/`: Directory containing vendor-specific contract terms in `.txt` format.
- `skills/penalty_logic/SKILL.md`: Custom Gemini CLI skill for calculating penalties.

## Building and Running

### Setup
Ensure `uv` is installed and run:
```bash
uv sync
cp .env.example .env
```
Configure `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` in `.env`.

### Execution
Run a self-check:
```bash
uv run python main.py --self-check
```

Audit a specific vendor:
```bash
uv run python main.py "Audit the account for Gujarat Steel Corp."
```

### Testing
Run the test suite:
```bash
uv run pytest
```

## Development Conventions

- **Structured Output:** The agent MUST return a `DiscrepancyReport` Pydantic model.
- **Audit Planning:** The agent is instructed to use `write_todos` to outline a 3-step audit plan before acting.
- **SQL Safety:** The `query_ledger` tool only allows `SELECT` statements.
- **Penalty Logic:** Late-delivery penalties are typically 5% of the invoice amount if delivery is more than 7 days late (verify against specific contract terms).
- **Naming:** Follow PEP 8 conventions. Use descriptive names for tools and variables.
- **Logging:** Use `loguru` for all application logging.

## Project Superpowers

This project includes a custom Gemini CLI skill:
- **Penalty Logic:** Located at `skills/penalty_logic/SKILL.md`. Use `activate_skill(name="penalty_logic")` to access specialized instructions for calculating delivery penalties.
