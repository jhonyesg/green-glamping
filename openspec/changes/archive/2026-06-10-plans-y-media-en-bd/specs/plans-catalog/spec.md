## ADDED Requirements

### Requirement: Tenant plan catalog

The system MUST provide a per-tenant catalog of plans/services stored in the
tenant's own database schema, with structured fields (name, slug, price,
description, included items, display order, active flag), editable from the
admin panel without code changes or restarts.

#### Scenario: Superadmin creates a new plan
- **WHEN** the superadmin submits the "Create plan" form with `slug="combo_5"`,
  `nombre="Combo 5"`, `precio_cop=290000`, `descripcion="Glamping+parapente+spa"`,
  `is_active=true`
- **THEN** the system MUST persist a row in `tenant_<slug>.offering` with those
  values and the plan MUST appear immediately in the listing at
  `/admin/plans`

#### Scenario: Plan price update is reflected in bot responses without restart
- **WHEN** the superadmin changes `combo_5.precio_cop` from 290000 to 320000
  in `/admin/plans` and a customer sends "cuánto cuesta el combo 5"
- **THEN** the next bot response MUST include the new price 320000 without
  any service restart, redeploy, or seed script run

#### Scenario: Inactive plan is not returned to customers
- **WHEN** a plan has `is_active=false` in the catalog
- **THEN** the system MUST NOT include it when rendering the price-list
  response and MUST NOT expose it via `GET /api/plans`

#### Scenario: Plan slug must be unique per tenant
- **WHEN** the superadmin attempts to create a plan with a slug that already
  exists for the tenant
- **THEN** the system MUST reject the creation with a clear error message
  naming the conflicting slug

### Requirement: Plan image and structured inclusions

Each plan MUST support a primary image (referenced from the media library)
and a structured list of inclusions stored as JSON, so the response template
can iterate over them.

#### Scenario: Plan references an uploaded image
- **WHEN** the superadmin uploads a JPG for `combo_5` from the plan form
- **THEN** the system MUST create a `media` row, store the file under
  `data/uploads/<tenant_slug>/`, and link the plan to it via `imagen_id`

#### Scenario: Plan inclusions are structured
- **WHEN** the superadmin edits `combo_5.incluye` to `["Vuelo parapente",
  "1 noche glamping montaña", "Sauna + jacuzzi", "Cena romántica"]`
- **THEN** the template `{{ for item in plan.incluye }}` MUST iterate over
  those four items in order

### Requirement: Display order

The system MUST allow the superadmin to set a `display_order` integer on
each plan, and the catalog response MUST list plans sorted ascending by
that field so the most relevant combo appears first.

#### Scenario: Reordering plans
- **WHEN** the superadmin sets `display_order=1` for `combo_5` and
  `display_order=2` for `solo_vuelo`
- **THEN** the rendered price list MUST show `combo_5` before `solo_vuelo`
