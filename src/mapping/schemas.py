from datetime import date
from typing import Optional

from pydantic import BaseModel


class PassportFields(BaseModel):
    document_no: Optional[str] = None
    type: Optional[str] = None
    country_code: Optional[str] = None
    surname: Optional[str] = None
    given_names: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    place_of_birth: Optional[str] = None
    date_of_issue: Optional[date] = None
    date_of_expiry: Optional[date] = None
    authority: Optional[str] = None
    mrz_line1: Optional[str] = None
    mrz_line2: Optional[str] = None


class MedicareFields(BaseModel):
    card_number: Optional[str] = None
    irn: Optional[int] = None
    full_name: Optional[str] = None
    valid_to: Optional[str] = None   # "MM/YYYY"


class DriverLicenceFields(BaseModel):
    licence_no: Optional[str] = None
    full_name: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    licence_expiry: Optional[date] = None
    licence_type: Optional[str] = None
    conditions: Optional[str] = None
    state: Optional[str] = "VIC"
