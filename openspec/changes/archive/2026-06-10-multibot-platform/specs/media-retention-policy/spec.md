## ADDED Requirements

### Requirement: Configurable retention per tenant

The system MUST allow each tenant to configure a
`retention_days` value (60, 90, 180, or 365). The system
MUST apply this value to inbound media under
`data/media/received/` and to conversation logs. The
system MUST reject retention values outside the allowed
set.

#### Scenario: Tenant sets 90 days
- **WHEN** the admin sets `retention_days: 90` for tenant
  Green Glamping
- **THEN** the nightly cleanup job MUST delete inbound
  media older than 90 days for that tenant only

### Requirement: Quarantine before hard delete

The system MUST move files scheduled for deletion to
`data/media/quarantine/` instead of hard-deleting them
immediately. The system MUST hard-delete quarantined
files 7 days later. The system MUST NOT auto-clean
quarantine without admin confirmation in production.

#### Scenario: File quarantined then deleted
- **WHEN** an inbound media file is older than the
  retention period
- **THEN** the system MUST move it to
  `data/media/quarantine/` and record the event in
  `audit_log`
- **WHEN** the file has been in quarantine for 7 days
- **THEN** the system MUST hard-delete it

### Requirement: Permanent assets never deleted

The system MUST NEVER delete files under
`data/media/sent/portfolio/`,
`data/media/sent/pregenerated/`, or
`data/media/sent/kb_assets/`. The system MUST treat
these as the tenant's permanent knowledge base assets.

#### Scenario: Cleanup skips permanent assets
- **WHEN** the nightly cleanup job runs
- **THEN** the system MUST NOT touch files under
  portfolio/, pregenerated/, or kb_assets/

### Requirement: TTS cache rotation

The system MUST keep auto-generated TTS audio for 30 days
if `use_count < 3`, for 60 days otherwise. The system
MUST hard-delete TTS audio that is not promoted to
predefined and exceeds these limits.

#### Scenario: Unused TTS purged at 30 days
- **WHEN** an auto-generated TTS audio has
  `use_count: 1` and is 30 days old
- **THEN** the system MUST quarantine it

### Requirement: Temp file cleanup

The system MUST hard-delete files under
`data/media/sent/temp/` after 24 hours. The system MUST
NOT quarantine temp files.

#### Scenario: Temp file deleted
- **WHEN** a file in `temp/` is older than 24 hours
- **THEN** the system MUST hard-delete it in the next
  cleanup cycle

### Requirement: Export retention

The system MUST keep `db_dumps/` for 30 days
(maintaining the last 5 even if older),
`conversation_logs/` for 90 days, and `reports/` for 365
days. The system MUST rotate these directories in the
nightly cleanup.

#### Scenario: Old db_dump pruned
- **WHEN** a `db_dumps/` file is older than 30 days
  AND there are more than 5 files in the directory
- **THEN** the system MUST delete the oldest one
