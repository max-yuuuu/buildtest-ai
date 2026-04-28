## ADDED Requirements

### Requirement: Generate page render images for replay
The system SHALL generate stable page render images for each ingested document so the frontend can replay evidence consistently across browsers and file formats.

#### Scenario: Ingestion produces per-page images
- **WHEN** a document ingestion job starts processing a document
- **THEN** the system renders page images (e.g., PNG) for each page that contains blocks
- **AND** each chunk references the corresponding `page_image_path` in `source_metadata`

### Requirement: Generate crop images for non-text blocks
The system SHALL generate crop images for non-text blocks (`image`, `table`, `equation`) to enable focused replay and downstream OCR/enhancement processing.

#### Scenario: Block crop is available for replay and OCR
- **WHEN** the parser emits a block with a bounding box on a page
- **THEN** the system generates a crop image for that block
- **AND** the chunk `source_metadata` contains `crop_image_path`

### Requirement: Replay assets are tenant-isolated and access-controlled
The system SHALL enforce tenant isolation for replay assets and only allow a user to access assets belonging to their own knowledge base documents.

#### Scenario: User requests replay asset for own document
- **WHEN** an authenticated user requests a replay asset referenced by their document chunk
- **THEN** the system returns the asset content

#### Scenario: User requests replay asset for another tenant
- **WHEN** an authenticated user requests a replay asset not belonging to them
- **THEN** the system rejects the request according to tenant isolation rules

