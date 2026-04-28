## MODIFIED Requirements

### Requirement: Asynchronous document ingestion workflow
The system SHALL process knowledge base document ingestion asynchronously. `POST /api/v1/knowledge-bases/{kb_id}/documents` MUST persist file metadata and storage path, set document status to `queued`, create an ingestion job, and return without waiting for embedding and vector upsert completion. The workflow MUST only be considered runnable when its dependent runtime services (database, queue backend, and active vector provider) are reachable under the current host/container startup mode.

#### Scenario: Upload returns queued document
- **WHEN** a user uploads a valid document to a knowledge base
- **THEN** the API returns success with `document_id` and status `queued` in bounded response time

#### Scenario: Worker completes ingestion
- **WHEN** the background worker processes a queued ingestion job successfully
- **THEN** the document status transitions to `completed` and chunk statistics are persisted

#### Scenario: Runtime dependency mismatch blocks ingestion readiness
- **WHEN** startup mode changes cause runtime addresses to mismatch actual service reachability
- **THEN** ingestion readiness is reported as not ready until dependent services are reachable with the effective runtime configuration
