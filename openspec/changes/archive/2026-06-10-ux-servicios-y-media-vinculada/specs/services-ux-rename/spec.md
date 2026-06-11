## ADDED Requirements

### Requirement: Catalog displayed as "Servicios" in admin UI

The admin panel MUST display the plan/offering catalog under the
"Servicios" label everywhere it appears to the superadmin: the
sidebar navigation entry, page titles, form headings, breadcrumbs
and button labels. The underlying table (`offering`), URL
(`/admin/plans/`), and code identifiers MUST stay unchanged so
existing bookmarks and code references keep working.

#### Scenario: Sidebar shows "Servicios"
- **WHEN** a superadmin loads any page under `/admin/`
- **THEN** the sidebar MUST show an entry labeled "🛎 Servicios"
  that links to `/admin/plans/`

#### Scenario: List page heading is "Servicios del catálogo"
- **WHEN** the superadmin opens `/admin/plans/?tenant=…`
- **THEN** the page heading MUST read "Servicios del catálogo"
  (not "Planes" or "Planes del catálogo")

#### Scenario: Form headings reference "servicio"
- **WHEN** the superadmin opens the create or edit form
- **THEN** the heading MUST read "Nuevo servicio" or "Editar
  servicio" and button labels MUST say "Crear servicio" /
  "Guardar"

#### Scenario: Internal table name unchanged
- **WHEN** the superadmin inspects the database
- **THEN** the table MUST still be named `offering` (not
  `services` or `plans_offered`) and the URL MUST still be
  `/admin/plans/`

### Requirement: Image selected from media library, not uploaded inline

The edit-service form MUST let the superadmin pick the cover
image from the tenant's media library (a `<select>` listing all
active image media rows for the tenant). There MUST NOT be a
file-upload control inside the service form. To change the
cover image, the superadmin uploads the file in
`/admin/media/` first and then selects it in the service form.

#### Scenario: Edit form shows media selector, not upload
- **WHEN** the superadmin opens `/admin/plans/{id}/edit?tenant=…`
- **THEN** the form MUST show a `<select name="imagen_id">`
  populated with active image media of the tenant, and MUST NOT
  show any `<input type="file">`

#### Scenario: Saving a new image_id updates the service
- **WHEN** the superadmin picks `carta_bebidas` from the
  selector and saves
- **THEN** `offering.imagen_id` for that service MUST be set to
  the media row's id, and the listing page MUST show the
  chosen image as the cover thumbnail

#### Scenario: No file uploaded in service form
- **WHEN** the superadmin submits the service edit form
- **THEN** the request MUST NOT contain any file field; if it
  does, the server MUST ignore it (no upload endpoint exists
  for the service form anymore)
