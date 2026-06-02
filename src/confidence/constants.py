AUTO_APPROVE_FLAG = "auto_approved"
REQUIRES_REVIEW_FLAG = "requires_manual_review"

BUSINESS_CARD_FIELDS = (
    "name",
    "phones",
    "email",
    "company",
    "position",
    "address",
    "website",
)

BUSINESS_CARD_IDENTITY_FIELDS = ("name", "company")
BUSINESS_CARD_CONTACT_FIELDS = ("email", "phones", "website")
BUSINESS_CARD_CONFIDENCE_FIELDS = BUSINESS_CARD_FIELDS

BUSINESS_CARD_SCHEMA = {
    "document_type": "business_card",
    "required_groups": [
        {
            "name": "identity",
            "min_required": 1,
            "fields": list(BUSINESS_CARD_IDENTITY_FIELDS),
        },
        {
            "name": "contact_method",
            "min_required": 1,
            "fields": list(BUSINESS_CARD_CONTACT_FIELDS),
        },
    ],
    "important_fields": list(BUSINESS_CARD_FIELDS),
    "confidence_fields": list(BUSINESS_CARD_CONFIDENCE_FIELDS),
    "optional_fields": ["address", "position", "company"],
}
