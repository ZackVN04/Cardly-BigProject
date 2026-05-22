# TODO(P5 — Hui): Implement map_document_fields entry point
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
    from src.mapping.mappers.passport_au import PassportMapper
    from src.mapping.mappers.medicare import MedicareMapper
    from src.mapping.mappers.driver_licence_vic import DriverLicenceMapper
    from src.mapping import normalizers, validators

    mapper_map = {
        DocType.PASSPORT_AU: PassportMapper,
        DocType.MEDICARE: MedicareMapper,
        DocType.DRIVER_LICENCE_VIC: DriverLicenceMapper,
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
        mapping_status="mapped" if not missing else "partial",
        mapper_version=mapping_constants.MAPPER_VERSION,
    )
    await doc.insert()
    return doc
