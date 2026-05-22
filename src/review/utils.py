# TODO(P7 — Khanh): Diff helpers for edit_log
from typing import Any


def build_edit_operation(field_name: str, old_value: Any, new_value: Any) -> dict:
    return {"field_name": field_name, "old_value": old_value, "new_value": new_value}
