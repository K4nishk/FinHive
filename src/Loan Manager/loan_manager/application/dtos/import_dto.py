from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class ImportPreviewDTO(BaseModel):
    total_new: int
    total_overwrite: int
    sample_overwrite_ids: list[str]
    file_path: str


class ImportResultDTO(BaseModel):
    inserted: int
    updated: int
    skipped: int
    errors: list[str]
