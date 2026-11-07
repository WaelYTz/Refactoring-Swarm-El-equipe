# 🤖 The Refactoring Swarm

<p>
  <img alt="top language" src="https://img.shields.io/github/languages/top/WaelYTz/Refactoring-Swarm-El-equipe?style=flat-square">
  <img alt="last commit" src="https://img.shields.io/github/last-commit/WaelYTz/Refactoring-Swarm-El-equipe?style=flat-square">
  <img alt="repo size" src="https://img.shields.io/github/repo-size/WaelYTz/Refactoring-Swarm-El-equipe?style=flat-square">
</p>


> **Multi-Agent AI System for Automated Python Code Refactoring**  
> IGL Lab 2025-2026 — ESI Algiers

A collaborative multi-agent system that automatically detects, fixes, and validates Python code quality issues using Google Gemini LLM, LangChain, and LangGraph. Three specialized AI agents work together in a self-healing pipeline to transform buggy code into clean, tested code.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Agents](#agents)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Usage](#usage)
- [Testing](#testing)
- [Telemetry & Monitoring](#telemetry--monitoring)
- [Team Roles](#team-roles)
- [License](#license)

---

## Overview

The Refactoring Swarm implements a **relay-style agent pipeline** where each agent has a specialized role:

1. **Listener (Auditor)** — Analyzes code and detects issues using Pylint + LLM
2. **Corrector (Fixer)** — Applies intelligent fixes using Gemini LLM
3. **Validator (Judge)** — Generates and runs tests to verify correctness

If tests fail, a **self-healing loop** sends error feedback back to the Corrector for retry, up to a configurable maximum number of iterations.

---

## Architecture

```
                    ┌─────────────────┐
                    │     START       │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    LISTENER     │ ← Analyzes code, detects issues
                    │   (Auditor)     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
              ┌─────│   DECISION      │─────┐
              │     │    NODE         │     │
              │     └─────────────────┘     │
              │                             │
        issues_found              no_issues_found
              │                             │
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │   CORRECTOR     │           │      END        │
    │    (Fixer)      │           │   (Success)     │
    └────────┬────────┘           └─────────────────┘
             │
             ▼
    ┌─────────────────┐
    │   VALIDATOR     │ ← Generates & runs tests
    │    (Judge)      │
    └────────┬────────┘
             │
        ┌────┴────┐
        │         │
   tests_pass  tests_fail
        │         │
        ▼         ▼
   ┌────────┐  ┌──────────────────────┐
   │  END   │  │  SELF-HEALING LOOP   │
   │SUCCESS │  │  → Back to CORRECTOR │
   └────────┘  └──────────────────────┘
```

The system supports two orchestration modes:
- **LangGraph** (default) — Uses a compiled state graph with conditional edges
- **Legacy** — Simple relay-based orchestrator with manual state machine

---

## Agents

| Agent | Role | Description |
|-------|------|-------------|
| **ListenerAgent** | Auditor 🔍 | Runs Pylint static analysis + LLM-powered issue detection on target Python files |
| **CorrectorAgent** | Fixer 🔧 | Receives issue reports and generates corrected code using Gemini LLM |
| **ValidatorAgent** | Judge ⚖️ | Generates semantic unit tests with LLM, runs them with pytest, triggers self-healing on failure |

All agents inherit from `BaseAgent` and implement the `run(context) → context` interface.

---

## Project Structure

```
Refactoring-Swarm-El-equipe/
├── main.py                        # Entry point, orchestrator, CLI, state machine
├── requirements.txt               # Python dependencies
├── check_setup.py                 # Environment verification script
├── .env.example                   # Template for API key configuration
│
├── src/
│   ├── agents/                    # AI Agent implementations
│   │   ├── base_agent.py          #   Abstract base class (BaseAgent)
│   │   ├── listener_agent.py      #   Auditor: code analysis & issue detection
│   │   ├── corrector_agent.py     #   Fixer: LLM-powered code correction
│   │   └── validator_agent.py     #   Judge: test generation & validation
│   │
│   ├── graph/                     # LangGraph execution graph
│   │   └── execution_graph.py     #   State graph with nodes & conditional edges
│   │
│   ├── prompts/                   # Prompt engineering & templates
│   │   ├── listener_prompts.py    #   Auditor analysis prompts
│   │   ├── corrector_prompts.py   #   Fixer correction prompts
│   │   ├── validator_prompts.py   #   Judge test generation prompts
│   │   └── context_manager.py     #   Token optimization & context preparation
│   │
│   ├── tools/                     # Shared tooling for agents
│   │   ├── sandbox.py             #   Security: path validation & sandboxing
│   │   ├── file_operations.py     #   Safe read/write/delete with security
│   │   ├── code_analyzer.py       #   Pylint wrapper for static analysis
│   │   └── test_runner.py         #   Pytest wrapper for test execution
│   │
│   └── utils/                     # Utilities
│       ├── logger.py              #   Experiment logging (JSON telemetry)
│       └── telemetry_dashboard.py #   Dashboard & HTML report generation
│
├── tests/                         # Test suite
│   ├── test_integration.py        #   End-to-end integration tests
│   ├── test_logger_quick.py       #   Logger validation tests
│   └── fixtures/                  #   Test data
│       ├── buggy_code/            #     Intentionally buggy Python files
│       │   ├── calculator.py
│       │   ├── data_processor.py
│       │   └── string_utils.py
│       └── expected_fixes/        #     Reference correct implementations
│           ├── calculator.py
│           ├── data_processor.py
│           └── string_utils.py
│
├── logs/
│   └── experiment_data.json       # Telemetry log (auto-generated)
│
└── telemetry_report.html          # HTML telemetry report (auto-generated)
```

---

## Setup & Installation

### Prerequisites

- **Python 3.10 or 3.11**
- **Google Gemini API Key** ([Get one here](https://aistudio.google.com/apikey))

### 1. Clone the Repository

```bash
git clone https://github.com/WaelYTz/Refactoring-Swarm-El-equipe.git
cd Refactoring-Swarm-El-equipe
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API Key

```bash
cp .env.example .env
```

Edit `.env` and add your Google Gemini API key:

```env
GOOGLE_API_KEY=AIzaSy...your-key-here
```

### 5. Verify Setup

```bash
python check_setup.py
```

---

## Usage

### Basic Run

```bash
# Refactor code in a target directory
python main.py --target_dir ./path/to/your/code
```

### Advanced Options

```bash
# With custom iteration limit and verbose output
python main.py --target_dir ./my_project --max_iterations 5 --verbose

# Dry run (analysis only, no changes)
python main.py --target_dir ./my_project --dry_run

# Show execution graph visualization
python main.py --show-graph

# Use legacy orchestrator instead of LangGraph
python main.py --target_dir ./my_project --use-legacy
```

### Quick Test with Fixtures

```bash
# Copy buggy code to a sandbox directory
mkdir -p sandbox/test_run
cp tests/fixtures/buggy_code/*.py sandbox/test_run/

# Run the swarm
python main.py --target_dir ./sandbox/test_run --verbose
```

### CLI Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--target_dir` | Directory containing Python files to refactor | *(required)* |
| `--max_iterations` | Max self-healing loop iterations | `10` |
| `--verbose` | Enable detailed output | `True` |
| `--dry_run` | Analysis only, no code modifications | `False` |
| `--show-graph` | Display the execution graph and exit | — |
| `--use-legacy` | Use legacy relay orchestrator | `False` |

---

## Testing

### Run Integration Tests

```bash
pytest tests/ -v
```

### Run Specific Test Suites

```bash
# Integration tests
pytest tests/test_integration.py -v

# Logger validation tests
pytest tests/test_logger_quick.py -v
```

The test suite validates:
- Fixture file existence and structure
- Buggy code quality scores (confirming issues exist)
- Experiment log format (`experiment_data.json`)
- Action type enum compliance
- LLM prompt logging requirements

---

## Telemetry & Monitoring

All agent interactions are logged to `logs/experiment_data.json` for scientific analysis and grading.

### View Dashboard

```bash
python src/utils/telemetry_dashboard.py
```

### Export HTML Report

```bash
python src/utils/telemetry_dashboard.py --export telemetry_report.html
```

### Log Entry Schema

Each log entry contains:

| Field | Description |
|-------|-------------|
| `id` | Unique entry identifier |
| `timestamp` | ISO 8601 timestamp |
| `agent` | Agent name (e.g., `Auditor_Agent`) |
| `model` | LLM model used (e.g., `gemini-2.5-flash`) |
| `action` | Action type enum (`ANALYSIS`, `FIX`, `CODE_GEN`, etc.) |
| `details` | Action-specific payload |
| `status` | `SUCCESS` or `FAILURE` |
| `input_prompt` | Full prompt sent to LLM |
| `output_response` | Full LLM response |

---

## Team Roles

| Role | Responsibility |
|------|----------------|
| **Lead Dev (Orchestrateur)** | Execution graph design, relay handover logic, CLI, state machine |
| **Auditor Agent Dev** | Listener agent — Pylint + LLM code analysis |
| **Fixer Agent Dev** | Corrector agent — LLM-powered code correction |
| **Judge Agent Dev** | Validator agent — semantic test generation & self-healing loop |
| **Toolsmith** | Sandbox security, file operations, Pylint/pytest wrappers |
| **Prompt Engineer** | System prompts, templates, context optimization, prompt versioning |
| **Data Officer** | Logger, telemetry dashboard, test fixtures, integration tests |

---

## Tech Stack

- **LLM**: Google Gemini 2.5 Flash (via `langchain-google-genai`)
- **Orchestration**: LangGraph (state graph with conditional edges)
- **Framework**: LangChain (LLM integration layer)
- **Static Analysis**: Pylint
- **Testing**: Pytest
- **Language**: Python 3.10/3.11

---

## License

This project is developed as part of the **IGL Lab 2025-2026** course at **ESI Algiers** (École nationale Supérieure d'Informatique).

---

*Built with 🤖 by El Equipe — ESI Algiers, IGL Lab 2025-2026*