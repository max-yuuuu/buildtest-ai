## ADDED Requirements

### Requirement: Layered compose runtime strategy
The system SHALL provide a layered Docker Compose strategy for monorepo runtime orchestration, separating shared service definitions, development overrides, production overrides, and infrastructure-only startup into independently composable files.

#### Scenario: Development compose stack is assembled predictably
- **WHEN** a developer starts the full development stack with the documented compose command
- **THEN** the runtime uses base + dev layers, includes hot-reload behavior for frontend and backend, and excludes production-only runtime constraints

#### Scenario: Production compose stack is assembled predictably
- **WHEN** an operator starts the production stack with the documented compose command
- **THEN** the runtime uses base + prod layers, excludes source bind mounts, and runs services with production startup commands

### Requirement: Multi-stage image targets for app services
The system SHALL define multi-stage Docker build targets for frontend and backend services, with explicit development and production runner targets, and SHALL allow worker service reuse of the backend production image target.

#### Scenario: Frontend production runner uses standalone artifacts
- **WHEN** the frontend production image is built
- **THEN** the final image contains only runtime artifacts required to serve the Next.js app and excludes source and development-only dependencies

#### Scenario: Backend production runner disables reload semantics
- **WHEN** the backend production image is started
- **THEN** the process runs without development reload flags and remains compatible with long-running container orchestration

### Requirement: Startup matrix and command contract
The system SHALL document and maintain a runtime command matrix covering all supported local workflows, including full-container development, infrastructure-only startup, and mixed host/container modes.

#### Scenario: Team can execute standard startup matrix without manual env surgery
- **WHEN** a user follows the documented startup matrix commands
- **THEN** each mode starts with deterministic environment loading and without requiring ad-hoc edits to secrets-bearing `.env` files
