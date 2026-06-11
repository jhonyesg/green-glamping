## ADDED Requirements

### Requirement: Auto-learner analyzes recent conversations and proposes KB changes

The system MUST run a background job (cron) that analyzes the
last N hours of conversations, identifies clusters of
messages that hit the fallback or had low LLM confidence, and
generates proposals to improve the knowledge base. Proposals
are stored in `public.learner_proposals` for admin review.

#### Scenario: Cron triggers analysis
- **WHEN** the scheduled time arrives (default: every 6 hours)
- **THEN** the system MUST gather the last 24h of messages that were matched by `fallback` OR had `confidence < 0.5`, group them by semantic similarity, and call the LLM to generate proposals

#### Scenario: Proposal to create new intent
- **WHEN** 4 messages semantically similar ("tienen wifi", "cómo es la señal", "hay internet", "wifi funciona") all hit fallback
- **THEN** the system MUST generate a `learner_proposal` with `kind = "create_intent"`, `payload = {"name": "wifi_info", "keywords": [...], "response": "..."}`, and `sample_messages = [...]` (the original 4 messages)

#### Scenario: Proposal to update existing intent
- **WHEN** 3 messages matched the `precio_general` intent but `confidence < 0.6` (LLM was uncertain)
- **THEN** the system MUST generate a `learner_proposal` with `kind = "update_intent"`, `payload = {"intent_name": "precio_general", "current_response": "...", "suggested_response": "..."}`, and `sample_messages = [...]`

#### Scenario: Proposal to deprecate duplicate intent
- **WHEN** 2 intents have > 0.8 cosine similarity in their `keywords_regex` and one has been hit < 5 times in the last 30 days
- **THEN** the system MUST generate a `learner_proposal` with `kind = "deprecate_intent"`, `payload = {"to_remove": "...", "to_keep": "..."}`

### Requirement: Proposals are reviewed by an admin

The system MUST NOT auto-apply any proposal without explicit
admin approval. Proposals remain in `status = "pending"` until
the admin acts on them via the dashboard at `/admin/learner`.

#### Scenario: Pending proposals visible
- **WHEN** the superadmin opens `/admin/learner`
- **THEN** the system MUST list all proposals with `status = "pending"`, showing kind, target intent name, sample messages count, and creation time

#### Scenario: Admin approves and creates new intent
- **WHEN** the superadmin clicks "Aprobar y crear" on a proposal of kind `create_intent`
- **THEN** the system MUST insert the new row in `kb_intents` with `source = "auto_learner"`, set the proposal `status = "applied"`, snapshot the previous version (none, since it's new), and log `intent_created_via_learner`

#### Scenario: Admin approves and updates existing intent
- **WHEN** the superadmin clicks "Aprobar" on a proposal of kind `update_intent`
- **THEN** the system MUST create a snapshot in `intent_versions` of the current intent state, apply the proposed `response` and/or `keywords_regex` to the live `kb_intents` row, set the proposal `status = "applied"`, and log `intent_updated_via_learner`

#### Scenario: Admin rejects a proposal
- **WHEN** the superadmin clicks "Rechazar" on any proposal
- **THEN** the system MUST set the proposal `status = "rejected"`, record `reviewed_by` and `reviewed_at`, and never re-propose the same cluster (memoization by message hash)

#### Scenario: Admin edits before approving
- **WHEN** the superadmin opens a proposal's diff view, edits the suggested response, and clicks "Aprobar con cambios"
- **THEN** the system MUST use the edited text (not the original proposal) when applying
