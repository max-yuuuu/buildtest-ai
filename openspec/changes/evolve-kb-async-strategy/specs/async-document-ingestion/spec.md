## ADDED Requirements

### Requirement: Asynchronous document ingestion workflow
The system SHALL process knowledge base document ingestion asynchronously. `POST /api/v1/knowledge-bases/{kb_id}/documents` MUST persist file metadata and storage path, set document status to `queued`, create an ingestion job, and return without waiting for embedding and vector upsert completion.

#### Scenario: Upload returns queued document
- **WHEN** a user uploads a valid document to a knowledge base
- **THEN** the API returns success with `document_id` and status `queued` in bounded response time

#### Scenario: Worker completes ingestion
- **WHEN** the background worker processes a queued ingestion job successfully
- **THEN** the document status transitions to `completed` and chunk statistics are persisted

### Requirement: Ingestion lifecycle and retry tracking
The system SHALL persist ingestion job lifecycle states (`queued`, `processing`, `completed`, `failed`) and MUST track attempts, error message, and processing timestamps for each job.

#### Scenario: Ingestion failure is recorded
- **WHEN** ingestion fails due to parsing, embedding, or vector write errors
- **THEN** the job status becomes `failed`, document status becomes `failed`, and the error context is persisted

#### Scenario: Retry creates new processing attempt
- **WHEN** a failed document ingestion is retried
- **THEN** the system records a new attempt and transitions status from `failed` to `queued` before reprocessing
