from datetime import datetime

from src.common.enums import DocType
from src.mapping.models import MappedDocument


async def map_document_fields(
    processing_id: str,
    doc_type: DocType,
    ocr_result: dict,
    vision_result: dict,
    user_id: str,
) -> MappedDocument:
    """Entry point called by pipeline/stages.py.

    Steps:
      1. Select mapper by doc_type
      2. mapper.extract() → extracted_fields
      3. normalize() → normalized_fields
      4. validate() → validation_results + missing_required_fields
      5. Persist and return MappedDocument
    """
    from src.mapping import constants as mapping_constants
    from src.mapping import normalizers, validators
    from src.mapping.mappers.business_card import BusinessCardMapper

    mapper_map = {
        DocType.BUSINESS_CARD: BusinessCardMapper,
    }

    mapper_cls = mapper_map.get(doc_type)
    if mapper_cls is None:
        from src.mapping.exceptions import UnknownDocType
        raise UnknownDocType(f"Unsupported doc_type: {doc_type}")

    mapper = mapper_cls(ocr_result=ocr_result, vision_result=vision_result)

    # Step 1: extract raw fields
    extracted = mapper.extract()

    # Step 2: normalize
    normalized = normalizers.normalize_fields(doc_type, extracted)

    # Step 3: validate
    validation_results, missing = validators.validate_fields(doc_type, normalized)

    from beanie import PydanticObjectId

    doc = MappedDocument(
        processing_id=processing_id,
        doc_type=doc_type,
        user_id=PydanticObjectId(user_id),
        extracted_fields=extracted,
        normalized_fields=normalized,
        validation_results=validation_results,
        missing_required_fields=missing,
        # field_block_refs: populated by mapper.extract(); enables P6 to look up
        # the OCR block confidence score for each mapped field.
        field_block_refs=getattr(mapper, "field_block_refs", {}),
        mapping_status="mapped" if not missing else "partial",
        mapper_version=mapping_constants.MAPPER_VERSION,
    )

    doc_data = {
        "processing_id": processing_id,
        "doc_type": doc_type,
        "user_id": PydanticObjectId(user_id),
        "extracted_fields": extracted,
        "normalized_fields": normalized,
        "validation_results": validation_results,
        "missing_required_fields": missing,
        "mapping_status": "mapped" if not missing else "partial",
        "mapper_version": mapping_constants.MAPPER_VERSION,
        "mapped_at": datetime.utcnow(),
    }

    existing = await MappedDocument.find_one(MappedDocument.processing_id == processing_id)
    if existing:
        for field_name, value in doc_data.items():
            setattr(existing, field_name, value)
        await existing.save()
        return existing

    doc = MappedDocument(**doc_data)

    await doc.insert()
    return doc

