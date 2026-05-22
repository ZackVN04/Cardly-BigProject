SUPPORTED_DOC_TYPES = ["passport_au", "medicare", "driver_licence_vic", "unknown"]

# Region labels used in AiVisionResult.detected_regions — must match mock_data exactly
REGION_LABELS_PASSPORT_AU = [
    "document_no", "type", "country_code", "surname", "given_names",
    "nationality", "date_of_birth", "sex", "place_of_birth",
    "date_of_issue", "date_of_expiry", "authority", "mrz_line1", "mrz_line2",
]

REGION_LABELS_MEDICARE = ["card_number", "irn", "full_name", "valid_to"]

REGION_LABELS_DRIVER_LICENCE_VIC = [
    "licence_no", "full_name", "address", "date_of_birth",
    "licence_expiry", "licence_type", "conditions", "state",
]
