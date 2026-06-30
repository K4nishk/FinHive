import json
from pathlib import Path
from typing import Any, Optional

from loan_manager.config import RECOVERY_FILE


class RecoveryService:
    def write(self, operation: str, data: dict[str, Any]) -> None:
        RECOVERY_FILE.write_text(
            json.dumps({"operation": operation, "data": data}),
            encoding="utf-8",
        )

    def clear(self) -> None:
        if RECOVERY_FILE.exists():
            RECOVERY_FILE.unlink()

    def exists(self) -> bool:
        return RECOVERY_FILE.exists()

    def read(self) -> Optional[dict[str, Any]]:
        if not self.exists():
            return None
        try:
            return json.loads(RECOVERY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None
