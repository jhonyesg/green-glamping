# llm-providers Specification

## Purpose
TBD - created by archiving change multibot-platform. Update Purpose after archive.
## Requirements
### Requirement: LLM provider interface

The system MUST define an `LLMProvider` interface with methods
for chat, transcribe, synthesize speech, and analyze image.
Each provider (MiniMax, OpenAI-compat, Anthropic) MUST
implement this interface.

#### Scenario: Provider chat invocation
- **WHEN** the classifier invokes the LLM router for tenant T
- **THEN** the router MUST return the provider configured for
  T and call its `chat(messages, tools)` method

### Requirement: Per-tenant provider configuration

The system MUST allow each tenant to configure one or more
LLM providers with API keys, models, base URLs, and
capability flags. The system MUST encrypt API keys at rest.

#### Scenario: Multiple providers configured
- **WHEN** tenant T has two providers configured (MiniMax
  active, OpenAI fallback)
- **THEN** the system MUST use MiniMax for all requests and
  fall back to OpenAI only on MiniMax errors

### Requirement: Intelligent STT routing

The system MUST inspect the active provider's `audio_input`
capability flag. If true, the system MUST pass audio bytes
directly to the LLM. If false, the system MUST use the
tenant's configured STT fallback (Whisper or equivalent).

#### Scenario: Multimodal LLM receives audio
- **WHEN** a customer sends a voice note and the tenant's
  provider has `audio_input: true`
- **THEN** the system MUST call `provider.transcribe(audio)`
  and obtain the transcription in a single roundtrip

#### Scenario: Non-multimodal LLM with Whisper fallback
- **WHEN** a customer sends a voice note and the tenant's
  provider has `audio_input: false`
- **THEN** the system MUST call the configured Whisper
  fallback and pass the resulting text to the classifier

### Requirement: Token usage tracking

The system MUST record LLM token consumption in the `messages`
table (`llm_tokens_used`) for every invocation. The system
MUST aggregate usage per tenant per day for billing and
metrics.

#### Scenario: Token usage aggregated
- **WHEN** an LLM call returns with `usage.total_tokens = 540`
- **THEN** the system MUST record 540 in `messages.llm_tokens_used`
  and increment the daily aggregate for the tenant

### Requirement: Capability introspection

The system MUST expose each provider's capabilities (text
input/output, audio input/output, image input, video input)
via a `get_capabilities()` method. The system MUST query
this method before deciding which API to call.

#### Scenario: Image sent to non-vision provider
- **WHEN** a customer sends an image and the provider has
  `image_input: false`
- **THEN** the system MUST download the image, run vision
  via the provider's vision endpoint if available, otherwise
  use a fallback vision service, and pass the description as
  text to the classifier

