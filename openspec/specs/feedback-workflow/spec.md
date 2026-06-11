# feedback-workflow Specification

## Purpose
TBD - created by archiving change multibot-platform. Update Purpose after archive.
## Requirements
### Requirement: Client feedback channels

The system MUST allow the tenant's representative
(acting through the panel) to submit four kinds of
feedback: mark a bot response as bad, suggest a new
intent, edit an existing response, and submit a free-text
note. Each feedback submission MUST create a
`feedback_tickets` row with status `pending`.

#### Scenario: Mark response as bad
- **WHEN** the user marks a bot response with "Está mal"
- **THEN** the system MUST create a `feedback_tickets`
  row referencing the original `messages.id` and the
  intent (if any) with type `bad_response`

### Requirement: Approval workflow

The system MUST surface pending feedback tickets in the
admin panel. The admin MUST be able to approve or reject
each ticket. On approval, the system MUST apply the
change (modify the response, create the new intent, etc.)
and notify the submitter. On rejection, the system MUST
mark the ticket `rejected` with a reason.

#### Scenario: Approving a new intent suggestion
- **WHEN** the admin approves a `new_intent` feedback
  ticket
- **THEN** the system MUST create a new `kb_intents` row
  with status `active`, link the ticket to the new
  intent, and notify the submitter

#### Scenario: Rejecting a bad response ticket
- **WHEN** the admin rejects a `bad_response` ticket
- **THEN** the system MUST set the ticket to `rejected`
  with the admin's reason, MUST NOT modify the intent,
  and MUST record the decision in `audit_log`

### Requirement: Editable responses with pending state

The system MUST save bot response edits as a pending
modification when the admin edits them via the panel.
The system MUST continue serving the original response
until the admin approves the change. The system MUST
display both old and new response text in the panel for
diff review.

#### Scenario: Pending response edit
- **WHEN** the admin edits the response of intent
  `info_combos`
- **THEN** the system MUST save a pending change, MUST
  continue serving the old response, and MUST show a
  diff in the panel

### Requirement: Free-text notes

The system MUST allow the client to submit a free-text
note via the panel (e.g., "clients are asking about
airport pickup"). The system MUST create a
`feedback_tickets` row with type `free_text` and surface
it in the admin queue.

#### Scenario: Client submits a note
- **WHEN** the client types a free-text note and clicks
  "Enviar"
- **THEN** the system MUST create a `feedback_tickets`
  row with the note text and type `free_text`

### Requirement: Feedback metrics

The system MUST provide metrics on feedback: average
resolution time, approval vs rejection ratio, top
intents receiving "bad" marks, and the most common
client suggestions.

#### Scenario: Top bad-response intents
- **WHEN** the admin views the metrics dashboard
- **THEN** the system MUST display the top 5 intents by
  count of `bad_response` tickets in the selected
  period

