## ADDED Requirements

### Requirement: Intents can declare attached media

Each intent in `kb_intents` MUST be able to declare 0..N media
attachments via a `response_media_ids` jsonb column. The intent
editor at `/admin/kb/{id}` MUST let the superadmin pick any
active media rows of the tenant (multi-select), persist the
list of ids, and the pipeline MUST attach them to the outbound
message when the intent matches.

#### Scenario: Edit form shows media multi-select
- **WHEN** the superadmin opens `/admin/kb/{id}?tenant=…`
- **THEN** the form MUST include a multi-select listing all
  active media of the tenant (with type/tamaño/descripción
  hint), and the options already saved in the intent MUST be
  pre-selected

#### Scenario: Saving attachments persists the list
- **WHEN** the superadmin picks `carta_bebidas` and
  `bienvenida_manana` from the multi-select and saves
- **THEN** `kb_intents.response_media_ids` MUST be
  `["carta_bebidas", "bienvenida_manana"]` (the keys) or the
  equivalent ids, depending on the chosen encoding

#### Scenario: Pipeline attaches the media
- **WHEN** the classifier matches an intent that has
  `response_media_ids=["carta_bebidas"]` and the bot is about
  to send a reply
- **THEN** the outbound message MUST include both the response
  text AND a media attachment for the `carta_bebidas` file
  (downloaded once and sent to the channel)

#### Scenario: No attachments means text-only
- **WHEN** an intent has `response_media_ids=[]` or NULL
- **THEN** the bot MUST send only the text response, identical
  to the pre-change behavior (zero regression)

### Requirement: Backward compatibility with single audio

The existing `response_audio_id` column on `kb_intents` MUST
continue to work. On migration, any non-null `response_audio_id`
MUST be backfilled into `response_media_ids` so that no audio
attachment is lost.

#### Scenario: Migration backfills audio
- **WHEN** alembic migration 004 runs and an intent has
  `response_audio_id=42` (referencing media id 42)
- **THEN** the same row MUST have
  `response_media_ids=[42]` (or the equivalent) after the
  migration, and the pipeline MUST still send the audio

#### Scenario: After backfill, response_audio_id stays
- **WHEN** the migration completes
- **THEN** `response_audio_id` MUST still be readable (no
  destructive change); both columns coexist for one release
  and `response_audio_id` is deprecated but functional
