## ADDED Requirements

### Requirement: Multibot as MCP server

The system MUST expose its core functions as MCP tools
over the Model Context Protocol. The server MUST be
available at a configurable endpoint (default `/mcp`)
and MUST require authentication via a tenant-scoped API
key.

#### Scenario: External agent calls send_message
- **WHEN** an external MCP client calls the
  `send_message` tool with valid tenant credentials
- **THEN** the system MUST send the message to the
  configured channel for the specified conversation and
  return a delivery confirmation

### Requirement: Exposed MCP tools

The system MUST expose the following MCP tools:
`send_message(tenant, channel, thread, content)`,
`get_conversation(tenant, thread)`,
`classify_intent(tenant, text)`,
`trigger_handoff(tenant, thread, reason)`,
`list_active_conversations(tenant)`,
`get_tenant_kb(tenant)`.

#### Scenario: List tools capability
- **WHEN** an MCP client connects to the server
- **THEN** the `tools/list` response MUST include all
  six tools with their JSON schemas

### Requirement: Exposed MCP resources

The system MUST expose the following MCP resources:
`kb://{tenant}/intents`,
`conversations://{tenant}/{thread}`,
`metrics://{tenant}/summary`. The system MUST enforce
tenant isolation in resource URIs.

#### Scenario: Resource access scoped to tenant
- **WHEN** an MCP client requests
  `kb://green_glamping/intents` with credentials for
  green_glamping
- **THEN** the system MUST return green_glamping's KB
  and MUST return 403 for any other tenant slug

### Requirement: Multibot as MCP client

The system MUST support consuming external MCP servers
(e.g., a CRM, a payment gateway, a custom calendar).
The system MUST load MCP client configurations from
`tenants.mcp_clients` (jsonb) and MUST allow per-tenant
tool discovery at startup.

#### Scenario: External CRM tool invoked
- **WHEN** the classifier decides it needs customer
  history from the configured CRM MCP server
- **THEN** the system MUST call the external MCP tool
  `get_customer_history(phone)` and use the result in
  the response generation
