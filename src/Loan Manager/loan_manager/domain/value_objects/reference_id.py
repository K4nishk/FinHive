import re
from dataclasses import dataclass

REFERENCE_ID_PATTERN = re.compile(r"^\d{4}_\d{2}_\d+$")

@dataclass(frozen=True)
class ReferenceId:
    value: str

    def __post_init__(self):
        if not REFERENCE_ID_PATTERN.match(self.value):
            raise ValueError(f"Invalid reference_id format: {self.value!r}. Expected YYYY_MM_<order>")

    def __str__(self) -> str:
        return self.value

    @classmethod
    def build(cls, year: int, month: int, order: int) -> "ReferenceId":
        return cls(f"{year:04d}_{month:02d}_{order:03d}" if order < 1000 else f"{year:04d}_{month:02d}_{order}")
