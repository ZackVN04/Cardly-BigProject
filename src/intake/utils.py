import hashlib
import random
import string
from datetime import datetime


def generate_processing_id() -> str:
    date_part = datetime.utcnow().strftime("%Y%m%d")
    rand_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"PRC-{date_part}-{rand_part}"


def sha256_of_file(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
