## ADDED Requirements

### Requirement: TTS with cloned voice per tenant

The system MUST support one or more cloned voices per tenant,
configured in the panel. The system MUST use the configured
voice when generating TTS audio at runtime.

#### Scenario: Single voice configured
- **WHEN** tenant T has one voice "warm_main" configured
- **THEN** all TTS generations for T MUST use that voice

### Requirement: TTS decision logic

The system MUST decide whether to use TTS based on: (a)
whether the response is from a pre-defined intent with a
pre-generated audio, (b) the text length, and (c) the
tenant's TTS mode setting (`off`, `long_only`, `always`).

#### Scenario: Pre-generated audio used
- **WHEN** an intent has `response_audio_id` set
- **THEN** the system MUST send the pre-generated audio
  directly and MUST NOT generate new TTS

#### Scenario: Long text triggers TTS in long_only mode
- **WHEN** TTS mode is `long_only` and the response text
  exceeds the configured minimum character count
- **THEN** the system MUST generate TTS audio and send it
  alongside the text

### Requirement: TTS cache and reuse

The system MUST hash the text content and look up existing
TTS audio in the cache before generating new audio. The
system MUST increment the `use_count` of cached audio on
each reuse.

#### Scenario: Same text cached
- **WHEN** the bot generates a TTS for text "El horario es
  9am a 6pm" and the same text is requested again
- **THEN** the system MUST serve the existing audio from
  cache and increment its `use_count`

### Requirement: Auto-promotion of frequent TTS to predefined

The system MUST auto-mark cached TTS audio as a promotion
candidate when its `use_count` reaches the configured
threshold (default 5). The system MUST surface these
candidates in the panel for the admin to approve.

#### Scenario: Frequent TTS marked as candidate
- **WHEN** a TTS audio's `use_count` exceeds 5
- **THEN** the system MUST set its `status` to
  `promotion_candidate` and display it in the panel TTS
  management screen

#### Scenario: Admin approves promotion
- **WHEN** the admin approves a promotion candidate
- **THEN** the system MUST move the audio file to
  `data/media/sent/pregenerated/`, link it to the source
  intent, and remove it from the auto cache

### Requirement: Voice variant rotation

The system MUST rotate voice selection deterministically
per turn when multiple voice variants are configured
(e.g., `warm_1`, `warm_2`, `energetic_1`). The system
MUST use this rotation to avoid monotonic output while
remaining predictable.

#### Scenario: Three variants configured
- **WHEN** tenant T has variants `warm_1`, `warm_2`,
  `energetic_1` and the bot generates three TTS messages
  in a conversation
- **THEN** the system MUST use `warm_1` for turn 1,
  `warm_2` for turn 2, and `energetic_1` for turn 3

### Requirement: TTS provider configurability

The system MUST support TTS generation via the tenant's
LLM provider (when it has TTS capability) or via a
dedicated TTS service. The system MUST record which
provider generated each audio in `media_assets`.

#### Scenario: LLM provider generates TTS
- **WHEN** the tenant's LLM provider has TTS capability and
  the system needs to generate audio
- **THEN** the system MUST call the provider's TTS
  endpoint and record the provider name in
  `media_assets`

#### Scenario: Fallback to dedicated TTS service
- **WHEN** the tenant's LLM provider has no TTS capability
- **THEN** the system MUST call the configured dedicated
  TTS service and record its name in `media_assets`
