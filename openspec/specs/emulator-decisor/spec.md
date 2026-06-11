# emulator-decisor Specification

## Purpose
TBD - created by archiving change multibot-platform. Update Purpose after archive.
## Requirements
### Requirement: Sandbox simulation endpoint

The system MUST provide an endpoint `POST /admin/simulate`
that accepts a tenant ID, a thread ID, and a synthetic
inbound message, then runs the full classifier pipeline
without sending any response to a real customer. The
endpoint MUST return the decision tree trace, the chosen
response, and the metrics.

#### Scenario: Simulate a known question
- **WHEN** the admin calls `/admin/simulate` with
  tenant=green_glamping, thread=sim_001, message="Cuánto
  cuesta combo 5?"
- **THEN** the system MUST return a JSON document with
  the trace (steps: anti-injection, regex match,
  handoff check, output format), the response, and
  metrics showing `llm_calls: 0`

### Requirement: Decision tree visualization

The simulator MUST return the decision tree as a
structured list of steps, each with a check name, result
(matched/not_matched/yes/no), elapsed milliseconds, and
optional context (matched intent, candidates count, etc.).
The panel MUST render this as a visual flowchart.

#### Scenario: Trace rendered as flowchart
- **WHEN** the admin views a simulation result
- **THEN** the panel MUST display each step as a node
  with arrows showing the path taken

### Requirement: Export simulation as test

The system MUST allow exporting a simulation result as a
pytest test case. The exported test MUST be a runnable
Python function that, when executed, performs the same
simulation and asserts the same outcomes.

#### Scenario: Export produces pytest file
- **WHEN** the admin clicks "Export as test" on a
  simulation
- **THEN** the system MUST generate a Python file with
  an `async def test_<name>()` function containing the
  input message, expected intent, expected matched_via,
  and latency upper bound

### Requirement: Safe side effects

The simulator MUST NOT write to production tables, MUST
NOT send messages to real channels, MUST NOT trigger real
handoff notifications, and MUST NOT modify LLM provider
usage counters. The simulator MAY write to a separate
`simulations` table for history.

#### Scenario: Simulation has no real effect
- **WHEN** the admin runs a simulation against a real
  tenant
- **THEN** the system MUST NOT create or modify rows in
  `messages`, `conversations`, `reservations`, or
  `handoff_events`

