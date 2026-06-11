# handoff-intelligent Specification

## Purpose
TBD - created by archiving change multibot-platform. Update Purpose after archive.
## Requirements
### Requirement: Configurable handoff rules per mode

The system MUST allow each tenant to configure handoff
triggers (H01-H07) independently per operation mode
(autonomous, assisted, hybrid). The system MUST resolve
which H01 definition to use at handoff time based on the
tenant's `operation_mode`.

#### Scenario: H01-ModoA vs H01-ModoB
- **WHEN** a customer in autonomous mode says "listo, voy
  a pagar"
- **THEN** the system MUST trigger H01-ModoA (handoff for
  payment only) and pass the pre-reservation to the human

#### Scenario: H01-ModoB early handoff
- **WHEN** a customer in assisted mode shows purchase
  intent
- **THEN** the system MUST trigger H01-ModoB (early
  handoff) and let the human handle availability, data,
  and payment

### Requirement: Pause windows for in-handoff conversations

The system MUST support three configurable time windows per
tenant: short pause (default 12h, bot silent), long pause
(default 48h, bot silent + alert), resume threshold (default
48h, bot takes over). The system MUST re-evaluate these
windows on every inbound message.

#### Scenario: Message during short pause
- **WHEN** a message arrives and the conversation is in
  handoff within the short-pause window
- **THEN** the system MUST NOT respond, MUST log the
  message, and MUST forward it to the human

#### Scenario: Message after resume threshold
- **WHEN** a message arrives more than the resume threshold
  hours after the last handoff resolution
- **THEN** the system MUST reset the in-handoff flag, MUST
  resume normal bot handling, and MUST log the resumption

### Requirement: Human notification

The system MUST notify the assigned human contact when a
handoff is triggered. The system MUST support notification
channels: Telegram push, SMS, email, and WhatsApp message.
The system MUST include the full conversation context in
the notification.

#### Scenario: Telegram push notification
- **WHEN** handoff H01 is triggered for tenant Green Glamping
- **THEN** the system MUST send a Telegram message to the
  configured human chat ID with the customer name, the
  intent that triggered handoff, and a deep link to the
  panel conversation view

### Requirement: requires_human per intent

The system MUST allow marking specific intents as
`requires_human`. When such an intent matches in hybrid
mode, the system MUST bypass normal flow and trigger an
immediate handoff.

#### Scenario: Corporate event intent
- **WHEN** an intent `reserva_evento_corporativo` is
  marked `requires_human` and a customer matches it
- **THEN** the system MUST NOT attempt availability check
  and MUST trigger handoff with reason "requires_human"

### Requirement: Conversation state tracking

The system MUST track conversation state in the
`conversations.state` field with the valid values:
`active`, `in_handoff`, `ready_for_payment`,
`awaiting_proof`, `confirmed`, `closed`,
`cancelled_by_user`, `cancelled_auto`,
`cancelled_by_human`. State transitions MUST be logged
in `handoff_events` and `audit_log`.

#### Scenario: State transition on handoff
- **WHEN** handoff is triggered
- **THEN** the system MUST set `conversations.state` to
  `in_handoff` (Modo B) or `ready_for_payment` (Modo A/C)
  and create a `handoff_events` row

### Requirement: Bot resumes conversation on resume threshold

The system MUST reset the conversation to `active` state
when the resume threshold is reached and a new message
arrives. The system MUST log the resumption event and
MUST process the message through the normal classifier
flow.

#### Scenario: Customer returns after 3 days
- **WHEN** a customer in handoff sends a new message 72
  hours after the last interaction
- **THEN** the system MUST mark the conversation as
  `active`, log the resumption, and respond via the
  classifier

#### Scenario: Customer returns after 3 days
- **WHEN** a customer in handoff sends a new message 72
  hours after the last interaction
- **THEN** the system MUST mark the conversation as
  `active`, log the resumption, and respond via the
  classifier

