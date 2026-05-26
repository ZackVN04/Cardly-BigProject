from src.common.enums import DocType

MAPPER_VERSION = "1.0.0"

REQUIRED_FIELDS: dict[str, list[str]] = {
    DocType.BUSINESS_CARD: ["full_name", "company", "position", "email", "phone"],
    DocType.PASSPORT_AU: [
        "document_no", "surname", "given_names", "nationality",
        "date_of_birth", "date_of_expiry",
    ],
    DocType.MEDICARE: ["card_number", "irn", "full_name", "valid_to"],
    DocType.DRIVER_LICENCE_VIC: [
        "licence_no", "full_name", "date_of_birth", "licence_expiry",
    ],
}
