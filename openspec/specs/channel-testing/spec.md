## ADDED Requirements

### Requirement: Credential validation on save

The system MUST validate channel credentials against the
provider's real API when the channel is saved, and display the
result without blocking the save.

#### Scenario: Telegram token validated
- **WHEN** a Telegram channel is saved with a bot token
- **THEN** the system MUST call `getMe` and display the resolved
  bot name (`@usuario`) on success, or a clear error on failure

#### Scenario: Username pasted instead of token
- **WHEN** the value saved as token starts with `@` or does not
  match the `digits:letters` token shape
- **THEN** the system MUST show a plain-language hint explaining
  the difference between the bot @name and the token, mentioning
  @BotFather

### Requirement: Connection test button (level 1)

Each configured channel MUST offer a "Probar conexión" action
that checks the provider state on demand and reports it in plain
language.

#### Scenario: Evolution instance not linked
- **WHEN** the test runs and Evolution reports state `close`
- **THEN** the system MUST explain that the number is not linked
  and offer the QR to scan

#### Scenario: Evolution service down
- **WHEN** the base URL does not respond
- **THEN** the system MUST report that the service is unreachable
  and suggest checking the docker deployment

### Requirement: Telegram webhook diagnosis and takeover

The system MUST detect when the bot's webhook is owned by another
platform and offer a one-click takeover.

#### Scenario: Foreign webhook detected
- **WHEN** `getWebhookInfo` returns a URL not belonging to this
  platform
- **THEN** the system MUST display the foreign URL, its last
  error message if any, and a "Tomar el control" action

#### Scenario: Takeover preserves pending messages
- **WHEN** the user confirms the takeover
- **THEN** the system MUST call `deleteWebhook` without dropping
  pending updates and activate the configured transport

### Requirement: End-to-end test (level 2)

The system MUST allow a full pipeline test per channel using a
per-tenant test destination, so a real reply arrives at the
operator's device.

#### Scenario: E2E test on Telegram
- **WHEN** the operator clicks "Prueba completa" with a test
  chat_id configured
- **THEN** the system MUST run a simulated inbound message through
  the same pipeline as production and send the real reply to the
  test chat, reporting intent and latency in the panel

#### Scenario: Missing test destination
- **WHEN** no test destination is configured for the tenant
- **THEN** the system MUST prompt for it inline (with help on how
  to obtain a chat_id) instead of failing silently
