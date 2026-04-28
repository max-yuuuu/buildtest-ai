## ADDED Requirements

### Requirement: Multimodal document parsing produces structured blocks
The system SHALL parse uploaded knowledge base documents into structured blocks that preserve modality and layout position, including `text`, `image`, `table`, and `equation` block types, each with page index and bounding box.

#### Scenario: Parse returns blocks with layout locators
- **WHEN** a user uploads a supported document (PDF, Office, image) to a knowledge base
- **THEN** the ingestion pipeline produces one or more blocks
- **AND** each block includes `block_type`, `page`, and `bbox_norm` (normalized 0..1 coordinates)

### Requirement: OCR is applied for images and scanned pages with multi-language support
The system SHALL apply OCR to image-derived content and scanned PDF pages with multi-language support and persist the extracted text as part of the block-to-chunk conversion output.

#### Scenario: OCR runs on image blocks
- **WHEN** the parser produces an `image`/`table`/`equation` block with a crop image asset
- **THEN** the system runs OCR on the crop asset using configured languages
- **AND** the extracted text is available for chunk content generation

#### Scenario: OCR fallback runs on scanned PDF pages
- **WHEN** a PDF page yields no usable text layer during parsing
- **THEN** the system runs OCR on that page image
- **AND** the extracted text is used to generate retrievable chunks instead of failing with empty content

### Requirement: Multimodal blocks are converted into retrievable chunks with modality templates
The system SHALL convert structured blocks into retrievable chunk text using modality-specific templates so that non-text content becomes searchable through embedding-based retrieval.

#### Scenario: Image block becomes a chunk with replayable source metadata
- **WHEN** an image block is processed during ingestion
- **THEN** the system generates a chunk text that includes OCR text and/or an optional caption field
- **AND** the chunk persists `source_metadata` fields sufficient for replay (`page`, `bbox_norm`, `page_image_path`, `crop_image_path`, `block_type`)

#### Scenario: Table block becomes a chunk with structured content
- **WHEN** a table block is processed during ingestion
- **THEN** the system generates a chunk text that includes OCR text and/or a table-to-markdown representation when available
- **AND** the chunk persists `source_metadata` including replay locators

