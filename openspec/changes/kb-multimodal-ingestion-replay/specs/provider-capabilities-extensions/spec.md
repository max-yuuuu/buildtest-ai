## ADDED Requirements

### Requirement: Providers can register OCR capability models
The system SHALL allow users to register OCR models under the existing Provider system so the ingestion pipeline can invoke OCR through a tenant-scoped, configurable model registry.

#### Scenario: Register OCR model for a provider
- **WHEN** a user registers an OCR model under an active provider
- **THEN** the system persists the model entry with capability type `ocr`
- **AND** the model can be referenced by knowledge base ingestion configuration

### Requirement: Ingestion invokes OCR through the provider registry
The system SHALL invoke OCR using the provider registry configuration rather than hardcoding an OCR backend, and MUST record the effective model identifier used for traceability.

#### Scenario: OCR call records model lineage
- **WHEN** ingestion runs OCR for an image block
- **THEN** the system calls the configured provider/model to obtain OCR text
- **AND** the produced chunk `source_metadata` records `generator`/`model_id` fields sufficient to trace which OCR model produced the text

### Requirement: Capability extension is forward-compatible for VLM and table understanding
The system SHALL define a forward-compatible capability mechanism so optional enhancements (VLM caption, table understanding, equation understanding) can be enabled per knowledge base without changing the retrieval lineage contract.

#### Scenario: Optional enhancement is disabled by default
- **WHEN** a knowledge base does not enable an optional enhancement capability
- **THEN** ingestion proceeds using OCR-only text for non-text blocks
- **AND** the chunk `source_metadata.modality` reflects the generation path (e.g., `ocr_text`)

