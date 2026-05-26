from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer


class CustomModel(BaseModel):
    """Base for all API request/response schemas. Enforces UTC ISO-8601 datetimes."""

    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def _serialize_datetimes(self, value: Any) -> Any:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.strftime("%Y-%m-%dT%H:%M:%S%z")
        return value
