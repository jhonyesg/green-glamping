# admin-panel-wizard Specification

## Purpose
TBD - created by archiving change multibot-platform. Update Purpose after archive.
## Requirements
### Requirement: Six-step onboarding wizard

The system MUST provide a wizard for new tenant onboarding
with six steps in order: (1) basic data, (2) operation
mode, (3) channel connection, (4) calendar source (only
for modes autonomous and hybrid), (5) initial assets, (6)
knowledge base + test. The system MUST prevent advancing
to the next step until the current step's required fields
are valid.

#### Scenario: Skipping step 4 in assisted mode
- **WHEN** the admin selects "Human manages" (assisted
  mode) in step 2
- **THEN** step 4 (calendar source) MUST be skipped
  automatically

#### Scenario: Required field missing
- **WHEN** the admin attempts to advance from step 1
  without filling the tenant name
- **THEN** the system MUST display an inline error and
  MUST NOT advance

### Requirement: Visual KB editor

The system MUST provide a screen to view, edit, create,
and delete intents. Each intent edit MUST create a pending
change that requires admin approval (status
`pending_approval`) before becoming active.

#### Scenario: Editing an existing intent
- **WHEN** the admin modifies an intent's response text
  and saves
- **THEN** the system MUST create a pending change and
  MUST NOT modify the live `kb_intents` row until approved

### Requirement: Conversation viewer and intervention

The system MUST provide a conversation list and detail
view. The detail view MUST show the full message history,
the matched intent (if any), and quick action buttons:
"mark good", "mark bad", "edit intent", "view reservation".

#### Scenario: Marking a response as bad
- **WHEN** the admin clicks "mark bad" on a bot response
- **THEN** the system MUST create a `feedback_tickets` row
  with type `bad_response` and MUST notify the admin in
  the feedback queue

### Requirement: requires_human toggle per intent

In the KB editor, the system MUST show a toggle to mark
each intent as `requires_human`. The system MUST display
a confirmation dialog when toggling on, requiring the
admin to enter a reason.

#### Scenario: Toggling requires_human on
- **WHEN** the admin toggles `requires_human` on for an
  intent
- **THEN** the system MUST prompt for a reason, MUST save
  it to `kb_intents.human_reason`, and MUST immediately
  apply the change in the classifier (no approval needed
  for this toggle)

### Requirement: Metrics dashboard

The system MUST provide a metrics dashboard per tenant
showing: total conversations, intents triggered, top
intents, average response latency, conversion rate by
mode, handoff counts, abandonments, TTS usage, and
LLM token consumption.

#### Scenario: Metrics aggregated daily
- **WHEN** the admin opens the dashboard on day N
- **THEN** the system MUST display aggregated metrics for
  the last 7, 30, and 90 days

### Requirement: Role-based access

The system MUST support at least two roles: `admin` (full
access) and `viewer` (read-only + metrics). The system
MUST reject write operations from viewer accounts.

#### Scenario: Viewer cannot edit KB
- **WHEN** a viewer attempts to save an intent edit
- **THEN** the system MUST return HTTP 403 and MUST NOT
  persist the change

