from enum import Enum

# Supported document types in this system — only business_card is implemented.
SUPPORTED_DOC_TYPES = ["business_card", "unknown"]

# Region labels for business card fields — must match mock_data and P4 output contract
REGION_LABELS_BUSINESS_CARD = [
    "name", "phone", "email", "web", "position", "company",
]

class BusinessCardScanStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
