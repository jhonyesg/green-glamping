## ADDED Requirements

### Requirement: Tenant isolation by schema

The system MUST isolate each tenant in a dedicated PostgreSQL
schema within a single database instance. The system MUST
inject a `search_path` per request to ensure all queries
operate within the correct tenant schema.

#### Scenario: Cross-tenant data access denied
- **WHEN** a request originates from tenant A and attempts to
  read data from tenant B's schema
- **THEN** the system MUST raise a permission error and the
  query MUST NOT return rows from any other tenant's schema

#### Scenario: Schema creation on tenant onboarding
- **WHEN** a new tenant is created via the admin wizard
- **THEN** the system MUST create a new schema named
  `tenant_<slug>`, run all base migrations within it, and
  return the new tenant's ID

### Requirement: Tenant context propagation

The system MUST resolve the tenant from the incoming webhook
or admin request and make it available throughout the request
lifecycle via an async context variable.

#### Scenario: Tenant resolved from webhook
- **WHEN** a webhook arrives at `/webhook/{channel}/{tenant_slug}`
- **THEN** the system MUST load the tenant by slug and bind
  it to the request context before invoking the classifier

#### Scenario: Tenant resolved from admin session
- **WHEN** an admin user logs into the panel
- **THEN** the system MUST bind the selected tenant to the
  session and reject access to other tenants' data

### Requirement: Tenant lifecycle states

The system MUST support tenant states: `provisioning`,
`active`, `suspended`, `archived`. The system MUST reject
webhook processing for tenants in any state other than
`active`.

#### Scenario: Suspended tenant webhooks
- **WHEN** a webhook arrives for a tenant in `suspended` state
- **THEN** the system MUST return HTTP 403 and log the event

### Requirement: Plan-based feature gating

The system MUST associate each tenant with a plan that defines
limits (max concurrent chats, channels included, LLM tokens
included, storage quota). The system MUST enforce these limits
at runtime.

#### Scenario: Concurrent chat limit exceeded
- **WHEN** an active conversation count for the tenant reaches
  the plan's max
- **THEN** the system MUST queue new messages and respond with
  a "high traffic" message if the queue exceeds a threshold

### Requirement: Tenant migration export

The system MUST provide a command that exports a tenant's full
data (schema + media references + KB) as a portable bundle
suitable for `pg_dump` and restore on another instance.

#### Scenario: Export tenant bundle
- **WHEN** an admin runs `multibot tenant export <tenant_id>`
- **THEN** the system MUST produce a `.sql` dump of the
  tenant's schema, a manifest of media asset paths, and a
  metadata file with tenant configuration
