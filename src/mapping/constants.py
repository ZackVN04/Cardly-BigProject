from src.common.enums import DocType

MAPPER_VERSION = "1.0.0"

REQUIRED_FIELDS: dict[str, list[str]] = {
    DocType.BUSINESS_CARD: ["name", "phone", "email"],
}
