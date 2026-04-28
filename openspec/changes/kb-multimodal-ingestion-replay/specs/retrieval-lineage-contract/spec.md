## MODIFIED Requirements

### Requirement: Retrieval response includes lineage fields
The retrieval API SHALL return per-hit lineage metadata including knowledge base identifier, document identifier, chunk locator, source metadata, score, and retrieved text. The `source` metadata MUST be sufficient to trace back to the originating document chunk and enable optional visual replay when available.

#### Scenario: Retrieve returns traceable hits
- **WHEN** a user calls `POST /api/v1/knowledge-bases/{kb_id}/retrieve` and hits are found
- **THEN** each hit includes identifiers and source fields sufficient to trace back to the originating document chunk
- **AND** for multimodal chunks, `source` includes replay locators such as `block_type`, `page`, `bbox_norm`, and replay asset references (e.g., `page_image_path`, `crop_image_path`)

