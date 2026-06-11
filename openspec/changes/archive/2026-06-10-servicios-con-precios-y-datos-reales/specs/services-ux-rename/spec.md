# Spec delta: services-ux-rename

## MODIFIED Requirements

### Requirement: Service catalog displays price from `precio_cop` in admin UI

**Replaces** the requirement `Service catalog displayed as "Servicios" in admin UI` from `openspec/changes/ux-servicios-y-media-vinculada/specs/services-ux-rename/spec.md`.

The service catalog MUST display each service with its `precio_cop` formatted in Colombian pesos (ej: `$30.000`, `$200.000`) in:
- The service list (`/admin/plans/`): column "Precio" with currency formatting.
- The create form (`/admin/plans/`): field "Precio desde" (label emphasizes "desde" to communicate it's a starting price, not a closed quote).
- The edit form (`/admin/plans/{id}/edit`): same field with the current value pre-filled.
- The JSON API (`/api/plans`): numeric `precio_cop` plus formatted `precio_cop_fmt` for display.

The price is **informational**: the platform displays it but does not process payments. The business owner closes the deal with the client through whatever channel they prefer.

#### Scenario: Service list shows formatted price
- **WHEN** the superadmin opens `/admin/plans/?tenant=…`
- **THEN** each row MUST show the service's `precio_cop` formatted as `$NNN.NNN` (dots as thousands separator, `$` prefix), e.g. `$30.000`, `$200.000`, `$290.000`

#### Scenario: Create form asks for price
- **WHEN** the superadmin fills the "Nuevo servicio" form
- **THEN** the form MUST include a numeric input labeled "Precio desde" (placeholder: `0` for free services) and accept decimal values

#### Scenario: Edit form pre-fills current price
- **WHEN** the superadmin opens `/admin/plans/{id}/edit?tenant=…`
- **THEN** the price field MUST be pre-filled with the current `precio_cop` value

#### Scenario: API includes formatted price
- **WHEN** the superadmin calls `GET /api/plans?tenant=…`
- **THEN** each service in the JSON MUST include both `precio_cop` (numeric, e.g. `200000.0`) and `precio_cop_fmt` (string formatted, e.g. `"$200.000"`)

#### Scenario: Price 0 is allowed for free services
- **WHEN** the superadmin saves a service with `precio_cop=0` (e.g. "Tour de cortesía", "Carta del restaurante" included in combos)
- **THEN** the service MUST be saved and displayed with price `$0` (the list and API), and the form MUST NOT block the save

#### Scenario: Price in response templates
- **WHEN** an intent template references `{{ p.precio_cop | currency_cop }}`
- **THEN** the rendered reply MUST show the price formatted as `$NNN.NNN` using the current `precio_cop` from the database (no hardcoded prices in `response_text`)

### Requirement: Service catalog still labeled "Servicios" in admin UI

This requirement is **preserved** from the original spec (no change). The label "Servicios" remains; the modification above only re-adds the price display.

#### Scenario: Sidebar still shows "Servicios"
- **WHEN** a superadmin loads any page under `/admin/`
- **THEN** the sidebar MUST still show an entry labeled "🛎 Servicios" linking to `/admin/plans/`

#### Scenario: Internal table still named "offering"
- **WHEN** the superadmin inspects the database
- **THEN** the table MUST still be named `offering` (not `servicios` or `services`) and the URL MUST still be `/admin/plans/`
