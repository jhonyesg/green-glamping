# multimodal-pipeline Specification

## Purpose
TBD - created by archiving change multibot-platform. Update Purpose after archive.
## Requirements
### Requirement: Inbound media normalization

The system MUST accept inbound messages containing
images, audio, video, and documents on every supported
channel. The system MUST download, classify, and store
the media in a uniform way regardless of source channel.

#### Scenario: Image received on Telegram
- **WHEN** a customer sends a photo on Telegram
- **THEN** the system MUST download the file via the
  Telegram bot API, store it locally, generate a
  thumbnail, and create a `message_attachments` row
  with `media_type: image`

### Requirement: Vision for images

The system MUST run vision analysis on inbound images
using the tenant's LLM provider (if multimodal) or a
fallback vision service. The system MUST record the
description in `message_attachments.vision_description`.

#### Scenario: Multimodal LLM vision
- **WHEN** the tenant's LLM provider has
  `image_input: true` and a customer sends an image
- **THEN** the system MUST call
  `provider.analyze_image(image, prompt)` and store the
  result

### Requirement: STT for audio

The system MUST transcribe inbound audio messages using
the STT routing described in the `llm-providers` spec.
The system MUST record the transcription in
`message_attachments.transcript`.

#### Scenario: Voice note transcribed
- **WHEN** a customer sends a 30-second voice note
- **THEN** the system MUST obtain the transcription via
  the configured STT path and store it in
  `message_attachments.transcript`

### Requirement: Video handling

The system MUST extract audio from inbound video
messages, transcribe it, and (optionally) extract a
key frame for vision analysis. The system MUST record
both the transcript and the frame description in
`message_attachments`.

#### Scenario: Customer sends a video
- **WHEN** a customer sends a 60-second video showing
  a location
- **THEN** the system MUST extract the audio track,
  transcribe it via STT, extract a representative
  frame, run vision on the frame, and store both
  artifacts plus the original video

### Requirement: Outbound media types

The system MUST support sending images, audio files,
video files, and documents as outbound media using
each channel's native media API. The system MUST NOT
use forward/reenvío for outbound media.

#### Scenario: Sending a portfolio image
- **WHEN** the bot decides to attach a portfolio image
  to a response
- **THEN** the system MUST upload (if needed) and send
  the image via the channel's media API with a caption,
  NOT as a forwarded message

