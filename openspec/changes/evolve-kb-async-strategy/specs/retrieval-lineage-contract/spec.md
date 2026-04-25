## ADDED Requirements

### Requirement: Retrieval response includes lineage fields
The retrieval API SHALL return per-hit lineage metadata including knowledge base identifier, document identifier, chunk locator, source metadata, score, and retrieved text.

#### Scenario: Retrieve returns traceable hits
- **WHEN** a user calls `POST /api/v1/knowledge-bases/{kb_id}/retrieve` and hits are found
- **THEN** each hit includes identifiers and source fields sufficient to trace back to the originating document chunk

### Requirement: Retrieval response includes strategy snapshot
The retrieval API SHALL include the effective retrieval strategy identifier and effective retrieval parameters used for the query, including defaults resolved from knowledge base configuration.

#### Scenario: Request omits optional retrieval parameters
- **WHEN** the request does not provide `top_k` or `similarity_threshold`
- **THEN** the response includes resolved parameter values from knowledge base defaults in the strategy snapshot

#### Scenario: Request overrides retrieval parameters
- **WHEN** the request provides `top_k` or `similarity_threshold`
- **THEN** the response includes the overridden values in the strategy snapshot
