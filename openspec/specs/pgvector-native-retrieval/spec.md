# pgvector-native-retrieval Specification

## Purpose
TBD - created by archiving change evolve-kb-async-strategy. Update Purpose after archive.
## Requirements
### Requirement: PostgreSQL connector uses native pgvector search
For `postgres_pgvector` knowledge bases, the system SHALL execute vector similarity search in PostgreSQL using pgvector-native operators and indexed vector columns, rather than in-memory Python similarity scoring, for all quick chat retrieval attempts including rewritten-query retries.

#### Scenario: Search executes in database
- **WHEN** a retrieve request targets a knowledge base backed by `postgres_pgvector`
- **THEN** the connector performs top-k similarity search through SQL/pgvector and returns ordered hits

#### Scenario: Retry attempt also executes in database
- **WHEN** quick chat performs a second retrieval attempt after query rewrite
- **THEN** the connector executes the second attempt using the same pgvector-native SQL retrieval path

### Requirement: pgvector dimension integrity
The system SHALL enforce vector dimension consistency between knowledge base configuration and stored/search query vectors for PostgreSQL-backed knowledge bases.

#### Scenario: Stored vector dimension mismatch
- **WHEN** ingestion produces vectors that do not match the knowledge base embedding dimension
- **THEN** the ingestion is rejected with failure status and a descriptive error

#### Scenario: Query vector dimension mismatch
- **WHEN** retrieve receives an embedding vector length different from knowledge base embedding dimension
- **THEN** the request fails with an explicit dimension mismatch error

