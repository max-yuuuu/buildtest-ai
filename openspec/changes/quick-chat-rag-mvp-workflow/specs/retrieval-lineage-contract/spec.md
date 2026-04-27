## MODIFIED Requirements

### Requirement: Retrieval response includes lineage fields
The retrieval API SHALL return per-hit lineage metadata including knowledge base identifier, document identifier, chunk locator, source metadata, score, and retrieved text, and SHALL provide stable identifiers that can be emitted as chat citation events.

#### Scenario: Retrieve returns traceable hits
- **WHEN** a user calls `POST /api/v1/knowledge-bases/{kb_id}/retrieve` and hits are found
- **THEN** each hit includes identifiers and source fields sufficient to trace back to the originating document chunk

#### Scenario: Chat stream emits citations from retrieval lineage
- **WHEN** quick chat uses retrieval hits to generate an answer
- **THEN** each emitted citation event references lineage identifiers that map back to the corresponding retrieval hit

### Requirement: Retrieval response includes strategy snapshot
The retrieval API SHALL include the effective retrieval strategy identifier and effective retrieval parameters used for the query, including defaults resolved from knowledge base configuration, and SHALL include retrieval attempt metadata when retries are performed.

#### Scenario: Request omits optional retrieval parameters
- **WHEN** the request does not provide `top_k` or `similarity_threshold`
- **THEN** the response includes resolved parameter values from knowledge base defaults in the strategy snapshot

#### Scenario: Request overrides retrieval parameters
- **WHEN** the request provides `top_k` or `similarity_threshold`
- **THEN** the response includes the overridden values in the strategy snapshot

#### Scenario: Quick chat performs retry after query rewrite
- **WHEN** the first retrieval attempt returns zero hits and a rewritten query triggers a second attempt
- **THEN** strategy snapshot metadata includes attempt count and effective parameters for each attempt
