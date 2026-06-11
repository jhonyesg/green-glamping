## ADDED Requirements

### Requirement: Tenant media library

The system MUST provide a per-tenant media library stored in the tenant's
own database schema, with files stored on local disk under
`data/uploads/<tenant_slug>/` and exposed as static URLs at
`/media/<tenant_slug>/<file>`, accessible from any plan or response
template via a unique `key`.

#### Scenario: Upload via admin form
- **WHEN** the superadmin uploads `carta_bebidas.jpg` with `key="carta_bebidas"`,
  `tipo="image"`, `descripcion="Carta de bebidas del restaurante"`
- **THEN** the system MUST store the file under
  `data/uploads/green-glamping/<hash>.jpg` and create a `media` row with
  the provided `key`, returning the public URL
  `/media/green-glamping/<hash>.jpg`

#### Scenario: Reference media by key in response
- **WHEN** an intent's template contains `{{ media_url("carta_bebidas") }}`
- **THEN** the rendered response MUST substitute the public URL of the file
  bound to that key, or an empty string if no media row matches

#### Scenario: Reject unsupported file type
- **WHEN** the superadmin uploads a `.exe` file
- **THEN** the system MUST reject the upload with HTTP 415 and a clear
  error message; only `image/*`, `audio/*`, and `application/pdf` MUST be
  accepted

#### Scenario: Reject oversized file
- **WHEN** the superadmin uploads a file larger than 50 MB
- **THEN** the system MUST reject the upload with HTTP 413 and a message
  stating the 50 MB per-file limit

### Requirement: Media deactivation preserves file

When the superadmin sets a media row to `is_active=false`, the system MUST
hide it from public URLs and from `media_url()` resolution, but MUST NOT
delete the underlying file from disk so it can be reactivated later.

#### Scenario: Deactivated media not served
- **WHEN** a media row has `is_active=false` and a request hits
  `/media/green-glamping/<hash>.jpg` directly
- **THEN** the system MUST return HTTP 404 (the file exists on disk but
  is not exposed while inactive)

#### Scenario: Reactivation restores public access
- **WHEN** the superadmin sets the same row back to `is_active=true`
- **THEN** the file MUST be served again at the same URL

### Requirement: Media audit metadata

Each media row MUST record the original filename, the uploader
(`uploaded_by` username), and the source (`uploaded` | `seed`) for
traceability.

#### Scenario: Seeded media records its origin
- **WHEN** the seed script imports an existing image from
  `data/clients/green-glamping/media/images/carta-bebidas.jpg`
- **THEN** the resulting media row MUST have `source="seed"` and
  `original_path` set to the legacy relative path
