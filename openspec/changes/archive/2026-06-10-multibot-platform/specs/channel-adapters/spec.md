## ADDED Requirements

### Requirement: Channel adapter interface

The system MUST define a `ChannelAdapter` interface with methods
to parse inbound messages, send outbound messages, send typing
indicators, download media, and verify webhook signatures. Each
concrete channel (WhatsApp official, WhatsApp unofficial,
Telegram, Webchat) MUST implement this interface.

#### Scenario: Inbound message parsed uniformly
- **WHEN** a webhook arrives from any supported channel
- **THEN** the system MUST normalize the payload to an
  `InboundMessage` with `tenant_id`, `channel`, `thread_id`,
  `user`, `content`, and `timestamp` fields

### Requirement: Outbound media sent as native

The system MUST send outbound images, audio, video, and
documents using the channel's native media-send API. The
system MUST NOT use forward/reenvío for outbound media.

#### Scenario: Outbound image via WhatsApp official
- **WHEN** the bot decides to send an image to a WhatsApp
  customer
- **THEN** the system MUST POST to Meta Cloud API with
  `type: "image"` and an `image: { link, caption }` payload
  using the tenant's public CDN URL

#### Scenario: Outbound audio via Telegram
- **WHEN** the bot decides to send an audio file to a Telegram
  user
- **THEN** the system MUST call `bot.send_audio(chat_id,
  audio_file, caption)` with the file opened as a binary
  stream

### Requirement: Webhook signature verification

The system MUST verify the webhook signature of every inbound
request. The system MUST reject requests with missing or
invalid signatures before any business logic runs.

#### Scenario: Meta webhook signature
- **WHEN** a request arrives at `/webhook/whatsapp_official/`
  with an `X-Hub-Signature-256` header
- **THEN** the system MUST compute HMAC-SHA256 of the raw body
  using the tenant's app secret and reject the request if the
  signature does not match

### Requirement: Per-tenant channel configuration

The system MUST store channel credentials per tenant in the
`channels` table with `credentials` encrypted at rest. The
system MUST support multiple active channels per tenant.

#### Scenario: Multiple channels for one tenant
- **WHEN** tenant Green Glamping has both WhatsApp official
  and Telegram channels active
- **THEN** the system MUST route inbound messages from each
  to the same conversation thread when the user identifier
  matches

### Requirement: Typing indicator

The system MUST send a typing indicator to the customer
before invoking the classifier when the configured response
latency budget exceeds 1 second. The system MUST suppress
the indicator for tenants that disable it in panel config.

#### Scenario: Long classifier latency
- **WHEN** the classifier expects to take longer than 1 second
  (e.g. LLM fallback path)
- **THEN** the system MUST send a typing/seen indicator
  immediately, then proceed with classification

### Requirement: Media download

The system MUST download inbound media files to local storage
under `data/media/received/{tenant_id}/{date}/{chat_id}/` and
record the storage path in `message_attachments`.

#### Scenario: Inbound image received
- **WHEN** a customer sends an image on WhatsApp
- **THEN** the system MUST download the file via the channel
  adapter, store it locally, generate a thumbnail, and create
  a `message_attachments` row referencing the storage path
