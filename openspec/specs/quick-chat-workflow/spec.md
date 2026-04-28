# quick-chat-workflow Specification

## Purpose
TBD - created by syncing change quick-chat-rag-mvp-workflow. Update Purpose after archive.
## Requirements
### Requirement: Quick chat SHALL execute a deterministic MVP chain
The system SHALL execute quick chat requests through a deterministic chain consisting of query normalization, retrieval, context assembly, streamed answer generation, citation emission, and finalization.

#### Scenario: Quick mode request is accepted
- **WHEN** a client sends a chat request with `mode=quick`
- **THEN** the system executes the MVP chain in the defined order and streams response events

### Requirement: Quick chat SHALL retry once on empty retrieval
The system SHALL perform at most one query rewrite and one additional retrieval attempt when the first retrieval attempt returns zero hits.

#### Scenario: First retrieval returns zero hits and second returns hits
- **WHEN** the first retrieval attempt returns no hits and rewritten query retrieval returns hits
- **THEN** the system assembles context from second-attempt hits and continues normal answer generation

#### Scenario: Both retrieval attempts return zero hits
- **WHEN** both initial and rewritten query retrieval attempts return no hits
- **THEN** the system generates a fallback answer without knowledge context and includes a clear uncertainty notice

### Requirement: Quick chat SHALL emit standardized stream lifecycle events
The system SHALL emit `start`, `token`, `citation`, `step`, `error`, and `done` lifecycle events that conform to the stream mapping contract.

#### Scenario: Successful quick chat run
- **WHEN** quick chat completes without internal error
- **THEN** the stream contains ordered lifecycle events ending with exactly one `done` event

