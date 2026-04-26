## ADDED Requirements

### Requirement: Ingestion notification center for asynchronous document processing
The system SHALL provide an in-app notification center via the header bell icon for asynchronous knowledge base document ingestion events. This notification center MUST be scoped per user and expose unread status for actionable follow-up.

#### Scenario: Show unread signal in header bell
- **WHEN** the current user has unread ingestion notifications
- **THEN** the header bell shows an unread indicator
- **AND** the indicator clears after the notification is marked read based on product-defined read policy

#### Scenario: Open notification panel
- **WHEN** the user clicks the header bell
- **THEN** the system shows recent ingestion notifications ordered by newest first
- **AND** each item includes event type, concise status text, and event timestamp

### Requirement: Generate notifications from ingestion lifecycle transitions
The system SHALL generate notification events from document ingestion lifecycle transitions so users can safely leave the page and still receive outcome feedback.

#### Scenario: Notify successful ingestion completion
- **WHEN** an ingestion job transitions to `completed`
- **THEN** the system creates a success notification linked to the related knowledge base and document
- **AND** the notification message indicates the document is ready for retrieval

#### Scenario: Notify ingestion failure
- **WHEN** an ingestion job transitions to `failed`
- **THEN** the system creates a failure notification linked to the related knowledge base and document
- **AND** the notification message includes diagnosable failure context or a clear path to details

#### Scenario: Notify long-running ingestion timeout or stall
- **WHEN** an ingestion job exceeds the configured long-running threshold
- **THEN** the system creates a warning notification indicating delayed processing
- **AND** duplicate warning notifications for the same job state window are suppressed

### Requirement: Notification item must be actionable
Each ingestion notification SHALL be actionable and route the user to the relevant workflow context to continue operation (e.g., verify chunks, retry failures, inspect job state).

#### Scenario: Navigate from notification to resource context
- **WHEN** the user clicks a notification item
- **THEN** the system navigates to the corresponding knowledge base and document context
- **AND** the target page can immediately present current document status without additional manual filtering

### Requirement: Tenant isolation and read-state consistency
The notification center SHALL enforce user-level data isolation and consistent read-state updates across polling cycles.

#### Scenario: Enforce notification isolation by user
- **WHEN** a user queries notifications or unread count
- **THEN** only notifications belonging to that user are returned
- **AND** cross-tenant notification access is denied by default

#### Scenario: Keep read-state stable across polling
- **WHEN** the frontend polls notification endpoints periodically
- **THEN** already read notifications remain read
- **AND** unread count stays consistent with stored notification state
