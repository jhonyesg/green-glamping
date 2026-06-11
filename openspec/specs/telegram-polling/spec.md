## ADDED Requirements

### Requirement: Polling transport for Telegram

The system MUST support receiving Telegram updates via long
polling (`getUpdates`) as an alternative to webhooks, requiring
no public URL.

#### Scenario: Channel works immediately after save
- **WHEN** a Telegram channel is saved with a valid token and
  transport `polling` (or `auto` without a public base URL)
- **THEN** the system MUST start a background poller for that
  tenant and messages sent to the bot MUST receive pipeline
  replies without any further configuration

#### Scenario: Pollers survive restart
- **WHEN** the application starts
- **THEN** it MUST start pollers for every active Telegram channel
  configured with polling transport, resuming from the persisted
  offset

### Requirement: Transport selection and mutual exclusion

Telegram channels MUST have a `transport` setting (`auto`,
`polling`, `webhook`) and the two transports MUST never be active
simultaneously for the same bot.

#### Scenario: Auto mode without public URL
- **WHEN** transport is `auto` and no public base URL is
  configured globally
- **THEN** the system MUST use polling

#### Scenario: Switching to webhook
- **WHEN** the transport is changed to `webhook` with a public
  base URL available
- **THEN** the system MUST stop the tenant's poller and call
  `setWebhook` with the tenant's webhook route and secret

#### Scenario: Webhook conflict detected while polling
- **WHEN** the poller receives HTTP 409 (webhook active)
- **THEN** it MUST stop, mark the channel state as conflicted, and
  surface the webhook-diagnosis action in the panel

### Requirement: Poller resilience

Pollers MUST tolerate transient failures without crashing the
application or losing their tenant association.

#### Scenario: Network error during polling
- **WHEN** `getUpdates` fails with a network error
- **THEN** the poller MUST retry with exponential backoff, capped,
  and log the condition without terminating
