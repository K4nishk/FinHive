import re
from dataclasses import dataclass

REPORT_ID_PATTERN = re.compile(r"^RPT_\d{8}_\d+$")

@dataclass(frozen=True)
class ReportId:
    value: str

    def __post_init__(self):
        if not REPORT_ID_PATTERN.match(self.value):
            raise ValueError(f"Invalid report_id format: {self.value!r}. Expected RPT_YYYYMMDD_<order>")

    def __str__(self) -> str:
        return self.value

    @classmethod
    def build(cls, date_str: str, order: int) -> "ReportId":
        # date_str: YYYYMMDD
        return cls(f"RPT_{date_str}_{order:03d}" if order < 1000 else f"RPT_{date_str}_{order}")
