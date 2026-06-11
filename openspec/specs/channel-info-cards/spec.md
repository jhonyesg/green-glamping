## ADDED Requirements

### Requirement: Non-technical info card per channel option

Every channel option in the panel (Telegram, WhatsApp oficial,
Evolution API, Baileys propio, WAHA) MUST offer an ⓘ action that
opens an information card written for a business owner, not a
developer.

#### Scenario: Card content
- **WHEN** the user opens a channel's info card
- **THEN** it MUST present: qué es, cómo funciona, ventajas,
  desventajas, costo aproximado, requisitos, y nivel de riesgo —
  in plain Spanish without jargon

#### Scenario: Official vs unofficial comparison
- **WHEN** the user opens the card of any WhatsApp option
- **THEN** the card MUST state explicitly whether it is official
  or unofficial, and what that implies (Meta approval and
  per-conversation cost vs. free with number-ban risk)

### Requirement: Risk disclosure for unofficial WhatsApp

Unofficial WhatsApp options MUST disclose the account-ban risk
and reference the mitigations available in the platform.

#### Scenario: Ban risk shown with mitigation
- **WHEN** the user reads the Evolution/Baileys/WAHA card
- **THEN** it MUST mention the ban risk in clear terms and note
  that enabling Humanización reduces detectable bot patterns
