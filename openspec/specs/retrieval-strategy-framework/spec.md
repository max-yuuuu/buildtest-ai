# retrieval-strategy-framework Specification

## Purpose
TBD - created by archiving change evolve-kb-async-strategy. Update Purpose after archive.
## Requirements
### Requirement: Retrieval strategy abstraction
The system SHALL provide a retrieval strategy interface that decouples strategy logic from knowledge base storage operations and supports selecting strategy by `strategy_id`.

#### Scenario: Naive strategy execution
- **WHEN** a retrieve request does not specify a strategy override
- **THEN** the system executes the configured default strategy and returns the strategy identifier in response metadata

#### Scenario: Explicit strategy selection
- **WHEN** a retrieve request specifies a supported `strategy_id`
- **THEN** the system dispatches retrieval through the corresponding strategy implementation

### Requirement: Unsupported strategy handling
The system SHALL reject unsupported strategy identifiers with explicit validation errors and MUST NOT silently fallback to a different strategy.

#### Scenario: Unknown strategy identifier
- **WHEN** a retrieve request provides an unknown `strategy_id`
- **THEN** the API responds with a client error that identifies the strategy as unsupported

### Requirement: Strategy trace output contract
Each retrieval strategy SHALL emit normalized execution metadata that can be persisted by evaluation workflows for replay and comparison.

#### Scenario: Evaluation consumes strategy metadata
- **WHEN** retrieval is invoked from an evaluation job
- **THEN** normalized strategy metadata is available to be attached to evaluation records

