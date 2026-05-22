# TODO(P7 — Khanh): Implement review schemas
from src.common.base_model import CustomModel


class EditRequest(CustomModel):
    edits: list[dict]


class ConfirmResponse(CustomModel):
    processing_id: str
    status: str
    finalized_at: str
    final_json: dict


class DryRunResponse(CustomModel):
    would_succeed: bool
    missing_required_fields: list[str] = []
    failed_validations: list[dict] = []


class FinalDocumentResponse(CustomModel):
    processing_id: str
    doc_type: str
    final_json: dict
    confirmed_at: str
