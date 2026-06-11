## ADDED Requirements

### Requirement: Media key auto-generated on upload

When a superadmin uploads a media file, the system MUST assign
its `key` automatically as `media_NNN` where NNN is the next
available three-digit integer for that tenant (1-padded, e.g.
`media_001`, `media_002`, …). The superadmin MUST NOT type a
key during upload. After upload, the superadmin MAY rename the
key to something semantic via the edit form.

#### Scenario: First upload gets media_001
- **WHEN** the superadmin uploads a JPG to a tenant that has no
  media rows
- **THEN** the system MUST assign `key="media_001"`, store the
  file under `data/uploads/<tenant>/<sha>.<ext>`, and the
  listing MUST show `media_001` as the new key

#### Scenario: Subsequent upload increments the counter
- **WHEN** the tenant already has rows with keys
  `media_001` and `media_005` (a gap from a previous deletion)
- **THEN** the next upload MUST be assigned `key="media_006"`
  (MAX + 1, not the first free integer)

#### Scenario: Upload form has no key field
- **WHEN** the superadmin opens `/admin/media/?tenant=…`
- **THEN** the upload form MUST NOT contain any text input
  for the key; the only required inputs are file + description

#### Scenario: Renaming a key is allowed
- **WHEN** the superadmin opens the edit form for a media row
  and changes the `key` field to `carta_bebidas`
- **THEN** on save, the row's `key` MUST be updated and any
  subsequent `{{ 'carta_bebidas' | media_url }}` Jinja filter
  MUST resolve to that row's URL

### Requirement: Media key validation still applies

The `key` field, even when auto-generated, MUST continue to
match the same validation pattern (`[a-zA-Z0-9_-]{1,150}`) when
the superadmin renames it manually. The uniqueness constraint
per tenant MUST still be enforced.

#### Scenario: Rename collision rejected
- **WHEN** the superadmin tries to rename `media_002` to
  `carta_bebidas` but `carta_bebidas` already exists for the
  tenant
- **THEN** the system MUST reject the save and surface a
  clear error "Ya existe otra media con esa key"
