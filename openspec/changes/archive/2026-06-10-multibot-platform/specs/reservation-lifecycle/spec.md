## ADDED Requirements

### Requirement: Reservation entity and states

The system MUST maintain a `reservations` table with status
values: `tentative`, `pending_payment`, `confirmed`,
`cancelled_by_user`, `cancelled_auto`, `cancelled_by_human`.
The system MUST reject status transitions that are not in
the allowed graph.

#### Scenario: Tentative to pending_payment
- **WHEN** the bot has confirmed availability and the
  customer says "listo, voy a pagar"
- **THEN** the system MUST set `reservations.status` to
  `pending_payment` and trigger handoff

#### Scenario: Invalid transition rejected
- **WHEN** the system attempts to set a `cancelled_auto`
  reservation to `confirmed`
- **THEN** the system MUST raise a state transition error
  and MUST NOT persist the change

### Requirement: Payment message template per tenant

The system MUST store a configurable payment message
template in `tenants.payment_message_template` with text
sections and media attachments. The system MUST substitute
customer variables (name, date, amount) before sending.

#### Scenario: Template substitution
- **WHEN** the bot sends the payment message to customer
  "Juan Pérez" for date "14 de junio" and amount "$200.000"
- **THEN** the system MUST render the template with these
  values and send the resulting text plus the configured
  QR images and audio

### Requirement: Payment proof detection

The system MUST run vision to determine if an image is a
payment receipt when a message arrives in
`ready_for_payment` or `pending_payment` state. The
system MUST NOT change state for non-receipt images.

#### Scenario: Receipt image detected
- **WHEN** a customer sends an image in
  `ready_for_payment` state and vision classifies it as a
  receipt with confidence > 0.7
- **THEN** the system MUST set `conversations.state` to
  `awaiting_proof`, MUST respond "Recibido, validando...",
  and MUST notify the human

#### Scenario: Non-receipt image
- **WHEN** a customer sends an image and vision classifies
  it as not a receipt
- **THEN** the system MUST ask the customer to send the
  actual receipt and MUST NOT change state

### Requirement: Human payment confirmation

The human contact MUST confirm or reject the payment via
the admin panel. The system MUST update the reservation
status and conversation state on confirmation.

#### Scenario: Human confirms payment
- **WHEN** the human clicks "Pago confirmado" in the
  panel
- **THEN** the system MUST set `reservations.status` to
  `confirmed`, `conversations.state` to `confirmed`, and
  MUST trigger the bot to send the final confirmation
  message to the customer

#### Scenario: Human rejects payment
- **WHEN** the human clicks "Pago no recibido" in the
  panel
- **THEN** the system MUST set `conversations.state` to
  `active`, MUST notify the customer via the bot that the
  payment was not received, and MUST NOT cancel the
  reservation

### Requirement: Automatic reminders

The system MUST send an automatic reminder to the customer
24 hours after entering `ready_for_payment` if no
comprobante has been received. The system MUST auto-cancel
the reservation 48 hours after entering `ready_for_payment`
if no confirmation has been received.

#### Scenario: 24h reminder sent
- **WHEN** a conversation has been in `ready_for_payment`
  for 24 hours with no receipt
- **THEN** the system MUST send a reminder message via the
  bot and log the reminder event

#### Scenario: 48h auto-cancel
- **WHEN** a conversation has been in `ready_for_payment`
  for 48 hours with no payment confirmation
- **THEN** the system MUST set the reservation to
  `cancelled_auto`, release the slot, and notify the human

### Requirement: Graceful close for non-buyers

The system MUST detect when a customer is not buying
(keywords: "solo preguntaba", "luego miro", "ah ok gracias",
silence after info, etc.) and MUST close the conversation
with a polite message without pursuing the customer.

#### Scenario: Customer says "luego miro"
- **WHEN** a customer responds "luego miro" or similar
  non-buying signal
- **THEN** the system MUST send a polite closing message
  ("Cuando quieras volver, aquí estaré") and MUST NOT
  schedule any follow-up reminders
