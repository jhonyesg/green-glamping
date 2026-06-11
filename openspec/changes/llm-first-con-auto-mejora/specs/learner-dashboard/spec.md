## ADDED Requirements

### Requirement: Learner dashboard lists pending proposals

The system MUST expose a learner dashboard at `/admin/learner`
listing all `learner_proposals` with `status = "pending"`, with
one-click actions to approve, edit, or reject.

#### Scenario: Dashboard loads
- **WHEN** the superadmin opens `/admin/learner?tenant=…`
- **THEN** the system MUST show a table of proposals with columns: kind, target intent, sample count, created at, confidence

#### Scenario: Filter by kind
- **WHEN** the superadmin clicks a tab "Nuevos intents" (or similar)
- **THEN** the dashboard MUST filter to show only proposals with `kind = "create_intent"`

### Requirement: Diff view shows current vs proposed

For `update_intent` and `create_intent` proposals, the system
MUST show a diff view at `/admin/learner/{id}` with the current
intent state (if any) on the left and the proposed state on the
right, with sample messages from the cluster shown above.

#### Scenario: Diff view for update proposal
- **WHEN** the superadmin opens a proposal of kind `update_intent` for `intent_name = "horarios"`
- **THEN** the page MUST show side-by-side: left = current `response_text` and `keywords_regex`; right = proposed versions; top = list of 3-5 sample messages that triggered the proposal

#### Scenario: Inline edit before approving
- **WHEN** the superadmin edits the proposed `response` field directly in the diff view and clicks "Aprobar con cambios"
- **THEN** the system MUST apply the edited text (not the original proposal) and record the change in the version history
