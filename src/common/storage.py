import os
import shutil
from pathlib import Path


async def save_file(source_path: str | Path, dest_path: str | Path) -> str:
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source_path), str(dest))
    return str(dest)


async def read_file(file_path: str | Path) -> bytes:
    with open(file_path, "rb") as f:
        return f.read()


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
