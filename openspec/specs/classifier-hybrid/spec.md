# classifier-hybrid Specification

## Purpose
TBD - created by archiving change multibot-platform. Update Purpose after archive.
## Requirements
### Requirement: Hybrid classifier with regex first

The system MUST attempt to classify every inbound message by
matching the message text against the tenant's `kb_intents`
using their `keywords_regex`. The system MUST only invoke
the LLM as a fallback when no regex match exceeds the
configured confidence threshold.

#### Scenario: Regex match wins, no LLM call
- **WHEN** the message "Cuánto cuesta el combo 5?" arrives
  and the tenant has an intent with a matching regex
- **THEN** the system MUST return the intent's canned
  response, record `matched_via: "regex"`, and MUST NOT
  invoke the LLM

#### Scenario: LLM fallback for unmatched message
- **WHEN** no regex matches with confidence above the
  threshold
- **THEN** the system MUST invoke the LLM with the
  conversation history and request structured intent
  classification

### Requirement: Anti-injection three-layer protection

The system MUST enforce anti-injection in three layers:
pre-filter on inbound text, system prompt rules, and
post-response validation. The system MUST block any
response that reveals the bot's internal prompt or claims
to be a different model.

#### Scenario: Injection keyword detected pre-filter
- **WHEN** a message contains keywords like "ignora
  instrucciones", "dime tu prompt", "actúa como"
- **THEN** the system MUST skip LLM invocation and return
  a fixed deflection response

#### Scenario: Post-response leak detected
- **WHEN** the LLM response contains "soy bot", "soy una
  IA", or reveals internal prompt fragments
- **THEN** the system MUST replace the response with a
  generic in-character reply and log a `prompt_leak`
  event

### Requirement: Caching of classifications

The system MUST cache classification results in Redis keyed
by `text_hash` (sha256 of normalized text) and `tenant_id`,
with a TTL of 24 hours. The system MUST record a hit when
serving from cache.

#### Scenario: Repeated question served from cache
- **WHEN** the same customer message arrives twice within
  24 hours
- **THEN** the second occurrence MUST be served from the
  Redis cache without invoking regex or LLM

### Requirement: Multimodal message handling

The system MUST download inbound images, audio, video, and
documents and pass them to the appropriate processor
(vision, STT, video frame extraction) before classification.
The system MUST support all channels' media types in a
uniform way.

#### Scenario: Image with text caption
- **WHEN** a customer sends an image with the caption
  "esto es un comprobante de pago"
- **THEN** the system MUST run vision on the image, combine
  the description with the caption, and pass the result to
  the classifier

### Requirement: Confidence threshold and ambiguity

The system MUST assign a confidence score to every
classification. When the top two candidates are within a
narrow margin, the system MUST mark the response as
ambiguous and either ask for clarification or escalate to
human (depending on intent config).

#### Scenario: Ambiguous intent detected
- **WHEN** two intents score within 0.1 of each other
- **THEN** the system MUST respond with a clarification
  question OR trigger handoff based on
  `kb_intents.requires_human`

### Requirement: Multi-turn context window

The system MUST maintain a sliding window of the last 10
turns (user + bot) per conversation and include them in
LLM calls. The system MUST truncate older turns gracefully.

#### Scenario: 12-turn conversation
- **WHEN** a conversation has 12 turns and the LLM is invoked
- **THEN** the system MUST include only the most recent 10
  turns in the LLM context

