# tool-registry-contract Specification

## Purpose
TBD - created by syncing change quick-chat-rag-mvp-workflow. Update Purpose after archive.
## Requirements
### Requirement: Tool registry SHALL provide a unified invocation contract
The system SHALL expose a unified tool contract for `api`, `mcp`, `skill`, and `cli` categories with normalized request/response shape, execution metadata, and error semantics.

#### Scenario: Tool is invoked through registry
- **WHEN** a workflow node invokes a registered tool by tool identifier
- **THEN** the registry executes the tool and returns a normalized result containing success status, output payload, latency, and trace metadata

### Requirement: Quick mode SHALL enforce tool allowlist
The system SHALL enforce a mode-specific allowlist such that quick mode can only invoke `api_retrieve` in MVP scope.

#### Scenario: Quick mode attempts non-allowlisted tool
- **WHEN** quick mode requests invocation of a tool other than `api_retrieve`
- **THEN** the system rejects invocation with a deterministic authorization-style tool error

### Requirement: Tool execution SHALL be observable in stream and logs
The system SHALL record tool call attempt, completion status, and latency for each invocation and expose step-level observability for downstream debugging and evaluation.

#### Scenario: Retrieval tool completes successfully
- **WHEN** `api_retrieve` returns results for a quick mode request
- **THEN** the system records tool execution metadata and emits corresponding `step` progress state

