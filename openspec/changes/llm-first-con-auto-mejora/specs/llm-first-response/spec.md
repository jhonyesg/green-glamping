## ADDED Requirements

### Requirement: LLM is always invoked before response

The system MUST invoke the LLM on every inbound message before
generating a response. The LLM receives as input: the system
prompt of the tenant, the user message, the last 10 turns of
conversation memory, the active service catalog (plans with
prices), the list of available intent names, and the active
handoff rules. The LLM MUST return a structured JSON response.

#### Scenario: LLM is invoked on every message
- **WHEN** a message arrives to a tenant with `llm_strategy.mode = "llm_first"`
- **THEN** the pipeline MUST call the LLM router and wait for the response before building the OutboundMessage

#### Scenario: LLM response shape
- **WHEN** the LLM is invoked
- **THEN** it MUST return a JSON object with fields: `intent` (string), `response` (string), `use_media_keys` (list of strings), `requires_human` (bool), `confidence` (float 0..1), `reasoning` (string)

#### Scenario: Intent name maps to existing kb_intent
- **WHEN** the LLM returns `{"intent": "info_servicios", ...}`
- **THEN** the pipeline MUST look up `kb_intents.intent_name = "info_servicios"` for the tenant, attach its `response_media_ids` and `handoff_rule` to the OutboundMessage

#### Scenario: Intent name not found
- **WHEN** the LLM returns an intent name that doesn't exist in `kb_intents` for the tenant
- **THEN** the pipeline MUST use the `response` field from the LLM directly (no fallback to a hardcoded intent), and log a warning `llm_intent_not_found`

### Requirement: Regex pre-filter bypasses LLM on high confidence

To control token costs, the system MUST check the regex
classifier first. If the regex matches with a score above the
configured `bypass_threshold` AND no other intent is within 10%
of the top score, the system MUST use the regex's matched
intent's hardcoded response directly, skipping the LLM call.

#### Scenario: Bypass when regex is clear
- **WHEN** the message is "Horarios?" and the regex matches `intent_name=horarios` with score=1.5 (well above threshold 0.9) and no other intent scores above 0.3
- **THEN** the system MUST use the `horarios` intent's `response_text` directly, MUST NOT call the LLM, and MUST set `matched_via = "regex_bypass"`

#### Scenario: LLM invoked when regex is ambiguous
- **WHEN** the regex matches two intents with scores 0.85 and 0.83 (within 10% of each other)
- **THEN** the system MUST invoke the LLM with the regex top-2 candidates as suggestions, and the LLM's JSON `intent` field wins

#### Scenario: Bypass threshold is configurable per tenant
- **WHEN** the tenant has `llm_strategy.bypass_threshold = 0.95`
- **THEN** only regex matches with score > 0.95 trigger the bypass; lower scores go to the LLM

### Requirement: LLM response is validated before sending

The system MUST validate the LLM JSON response before sending it
to the customer. Validation layers (in order):

1. **JSON parse** — if the LLM output is not valid JSON, the
   system MUST fall back to the regex match's response (or
   the default fallback response if regex also failed).
2. **Schema check** — required fields `intent`, `response` MUST
   be present and non-empty. If missing, fall back.
3. **Safety check** — the `response` text MUST NOT contain
   phrases like "soy bot", "soy una IA", "como modelo de
   lenguaje", or fragments of the system prompt. If detected,
   the response is replaced with a generic in-character reply
   and a `prompt_leak` event is logged.
4. **Confidence threshold** — if `confidence < 0.4`, the system
   SHOULD escalate to a human via handoff_rule.

#### Scenario: Malformed JSON falls back gracefully
- **WHEN** the LLM returns text that is not valid JSON
- **THEN** the system MUST log `llm_json_parse_failed`, fall back to the regex match's response (or the hardcoded FALLBACK_RESPONSE if regex didn't match), and continue serving the customer

#### Scenario: Prompt leak blocked
- **WHEN** the LLM response contains "soy una inteligencia artificial"
- **THEN** the system MUST replace the response with "¡Hola! 👋 ¿En qué te puedo ayudar?" and log `prompt_leak` with the original response (truncated to 200 chars)

#### Scenario: Low confidence escalates to human
- **WHEN** the LLM returns `confidence: 0.25`
- **THEN** the system MUST set `requires_human = true` regardless of what the LLM said, and trigger the handoff flow

### Requirement: LLM usage is rate-limited per tenant

To control costs, the system MUST enforce rate limits on LLM
invocations, configurable per tenant in `bot_config.llm_strategy`.

#### Scenario: Per-message cap
- **WHEN** `llm_strategy.max_llm_calls_per_message = 1` and a single inbound message has triggered 2 LLM calls (e.g. one for intent, one for safety rephrase)
- **THEN** the system MUST NOT make the 2nd call and fall back to the regex match's response

#### Scenario: Per-conversation hourly cap
- **WHEN** `llm_strategy.max_llm_calls_per_conversation_per_hour = 20` and a single conversation has already triggered 20 LLM calls in the past hour
- **THEN** the 21st message in that conversation MUST NOT call the LLM and fall back to the regex match's response
