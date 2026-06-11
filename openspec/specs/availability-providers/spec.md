# availability-providers Specification

## Purpose
TBD - created by archiving change multibot-platform. Update Purpose after archive.
## Requirements
### Requirement: Availability provider interface

The system MUST define an `AvailabilityProvider` interface
with methods: `is_available(date, duration)`, `get_available_
slots(month, duration)`, `reserve_slot(date, metadata)`,
`release_slot(ref)`, `sync()`. The system MUST support four
concrete implementations: local table, Google Calendar,
iCal URL, and MCP server.

#### Scenario: Local table availability check
- **WHEN** the bot checks availability for a date via the
  local table provider
- **THEN** the system MUST query `availability_slots` for
  that date and return true if any slot is not blocked

#### Scenario: Google Calendar availability check
- **WHEN** the bot checks availability via Google Calendar
- **THEN** the system MUST use the Google Calendar API with
  the tenant's OAuth credentials and the configured
  `calendar_id`

### Requirement: Local slot cache

The system MUST maintain a `availability_slots` table that
mirrors the external source. The system MUST sync this table
on a configurable interval and on demand. The bot MUST
always query the local table, not the external API
directly, to keep latency low.

#### Scenario: Sync from Google Calendar
- **WHEN** the sync interval (default 15 minutes) elapses
- **THEN** the system MUST fetch events from Google
  Calendar, mark slots as blocked or free, and update
  `availability_slots`

### Requirement: Slot reservation and release

The system MUST support reserving a slot when a customer
confirms intent and releasing it on cancellation or timeout.
The system MUST prevent double-booking via a uniqueness
constraint on `(tenant_id, slot_id)` in `reservations`.

#### Scenario: Customer confirms date
- **WHEN** a customer confirms "el 14 de junio, listo"
  in autonomous mode
- **THEN** the system MUST call `provider.reserve_slot()`
  and create a `reservations` row with `status: tentative`

#### Scenario: Reservation auto-cancelled after 48h
- **WHEN** a tentative reservation has no payment
  confirmation after 48 hours
- **THEN** the system MUST call `provider.release_slot()`,
  set the reservation to `cancelled_auto`, and notify the
  human contact

### Requirement: Source credentials encryption

The system MUST encrypt `availability_sources.credentials`
(jsonb) at rest. The system MUST support OAuth refresh
token rotation for Google Calendar sources.

#### Scenario: Google OAuth token refresh
- **WHEN** a Google Calendar API call returns 401
- **THEN** the system MUST use the refresh token to obtain
  a new access token, persist it, and retry the original
  call

### Requirement: Buffer between slots

The system MUST respect a configured buffer (default 30
minutes) between reservations when computing available
slots. The buffer prevents back-to-back bookings without
cleanup time.

#### Scenario: Slot blocked by buffer
- **WHEN** slot 14:00-15:00 is reserved and buffer is 30
  minutes
- **THEN** the system MUST mark slot 15:30-16:30 as the
  next available, not 15:00-16:00

