# vector-runtime-switch-guard Specification

## Purpose
TBD - created by syncing change docker-mono-dev-prod-runtime-strategy. Update Purpose after archive.
## Requirements
### Requirement: Vector runtime switch guard for supported providers
The system SHALL provide runtime switch guardrails for vector infrastructure with support scoped to `postgres_pgvector` and `qdrant`, and SHALL reject assumptions that unsupported vector providers are locally runnable in this phase.

#### Scenario: Supported providers are explicitly bounded
- **WHEN** runtime switch rules are evaluated for local and compose workflows
- **THEN** only `postgres_pgvector` and `qdrant` are treated as guaranteed runnable providers

### Requirement: Two-layer vector availability verification
The system SHALL verify vector runtime readiness through both infrastructure health and application-level connection checks against the active vector DB configuration.

#### Scenario: Infrastructure health passes but app probe fails
- **WHEN** vector infrastructure containers are healthy but the active vector configuration is invalid
- **THEN** the guard reports failure and blocks readiness claims for vector-dependent workflows

#### Scenario: Active vector provider probe succeeds
- **WHEN** the active vector configuration points to a reachable provider with valid credentials and routing
- **THEN** the guard reports vector runtime ready for ingestion and retrieval workflows

### Requirement: Switch validation after active provider change
The system SHALL run a post-switch validation flow after changing active vector configuration to ensure the new provider can serve baseline knowledge-base operations.

#### Scenario: Provider switch from postgres_pgvector to qdrant
- **WHEN** a user activates a qdrant vector configuration after previously using postgres_pgvector
- **THEN** post-switch validation confirms provider connectivity and marks runtime state as ready only on success
