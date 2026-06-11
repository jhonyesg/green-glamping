## ADDED Requirements

### Requirement: Humanized outbound delivery

The system MUST be able to deliver bot replies imitating natural
human writing: splitting long replies into bubbles, showing the
typing indicator, and pacing sends with length-proportional,
randomized delays.

#### Scenario: Long reply split into bubbles
- **WHEN** humanization is enabled and a reply contains multiple
  paragraphs
- **THEN** the system MUST send it as separate messages (up to the
  configured maximum), each preceded by a typing indicator and a
  delay proportional to its word count with random jitter

#### Scenario: Humanization disabled
- **WHEN** humanization is disabled for the tenant or for the
  message's channel type
- **THEN** the reply MUST be sent as a single immediate message
  (current behavior)

### Requirement: Per-tenant humanization configuration

Humanization MUST be configurable per tenant in `bot_config` and
editable from the Flow view as a 🎭 node, including: enabled,
applicable channel types, bubble splitting, max bubbles, typing
speed (wpm), and min/max bounds for typing and pause delays.

#### Scenario: Configured from the Flow view
- **WHEN** the operator clicks the 🎭 Humanización node
- **THEN** a panel MUST allow editing all humanization settings,
  persisted in the tenant's `bot_config` and applied to the next
  message without restart

#### Scenario: Channel-scoped application
- **WHEN** humanization lists only `whatsapp_unofficial` in its
  channels
- **THEN** WhatsApp replies MUST be humanized while Telegram
  replies are sent immediately

### Requirement: Latency metrics unaffected

Humanization delays MUST NOT distort pipeline latency metrics.

#### Scenario: Recorded latency excludes pacing
- **WHEN** a humanized reply is delivered with pacing delays
- **THEN** `messages.latency_ms` MUST record only the processing
  latency (pipeline), not the humanized delivery time

### Requirement: Simulator shows the bubble plan

The simulator and Flow test MUST display how a reply would be
humanized without waiting for real delays.

#### Scenario: Bubble plan preview
- **WHEN** a message is simulated and humanization is enabled
- **THEN** the result MUST include the planned bubbles with their
  computed typing/pause times, rendered instantly
