# chat-mode-routing Specification

## Purpose
TBD - created by syncing change quick-chat-rag-mvp-workflow. Update Purpose after archive.
## Requirements
### Requirement: Chat API SHALL accept explicit mode routing
The chat API SHALL accept a `mode` field with supported values `quick`, `agent`, and `data`, and SHALL route requests according to mode-specific handlers.

#### Scenario: Request without mode
- **WHEN** a client sends a chat request without `mode`
- **THEN** the system defaults to `quick` mode routing

### Requirement: Non-MVP modes SHALL return explicit not-implemented response
For MVP scope, the system SHALL only enable `quick` mode and SHALL return a deterministic `MODE_NOT_IMPLEMENTED` error for `agent` and `data` requests.

#### Scenario: Agent mode request in MVP phase
- **WHEN** a client sends a chat request with `mode=agent`
- **THEN** the system returns an explicit `MODE_NOT_IMPLEMENTED` response without entering quick workflow

#### Scenario: Data mode request in MVP phase
- **WHEN** a client sends a chat request with `mode=data`
- **THEN** the system returns an explicit `MODE_NOT_IMPLEMENTED` response without entering quick workflow

### Requirement: Mode routing SHALL preserve stable response contract
The API SHALL preserve the same top-level response envelope and stream contract across modes so future mode enablement does not require client protocol changes.

#### Scenario: Quick mode success response
- **WHEN** quick mode executes successfully
- **THEN** the stream schema and event naming remain compatible with clients that will later consume agent/data modes

