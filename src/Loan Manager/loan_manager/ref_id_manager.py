"""RefIdManager — class-based reference ID generator matching the test API.

Tests expect:
    manager = RefIdManager(meta_path=meta_path)
    ref_id  = manager.next_ref_id(year, month)   -> str
    manager.reset_counter(year, month)            -> None

Meta CSV schema: year_month, counter
"""
import csv
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

_META_FIELDNAMES = ["year_month", "counter"]


class RefIdManager:
    """Generates and persists reference IDs in YYYY_MM_<order> format.

    Args:
        meta_path: Path to the loans_meta.csv file.  The file is created
                   automatically on the first call to next_ref_id().
    """

    def __init__(self, meta_path: Path) -> None:
        self._meta_path = meta_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def next_ref_id(self, year: int, month: int) -> str:
        """Return the next reference_id for the given year and month.

        Format: YYYY_MM_<order>
        - Order is zero-padded to 3 digits for values 001-999.
        - Beyond 999 the order is written without zero-padding (e.g. 1000).
        - If the counter for YYYY_MM is absent (new month or after reset),
          the first ID gets order 001.
        """
        ym = f"{year:04d}_{month:02d}"
        meta = self._read_meta()
        current = meta.get(ym, 0)
        next_order = current + 1

        if next_order <= 999:
            order_str = f"{next_order:03d}"
        else:
            order_str = str(next_order)

        ref_id = f"{ym}_{order_str}"

        meta[ym] = next_order
        self._write_meta(meta)

        logger.info("Generated reference_id: %s", ref_id)
        return ref_id

    def reset_counter(self, year: int, month: int) -> None:
        """Reset the counter for the given year/month bucket to zero.

        The next call to next_ref_id() for that bucket will return _001.
        """
        ym = f"{year:04d}_{month:02d}"
        meta = self._read_meta()
        if ym in meta:
            del meta[ym]
        self._write_meta(meta)
        logger.info("Counter reset for %s", ym)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_meta(self) -> Dict[str, int]:
        """Read loans_meta.csv; return mapping of 'YYYY_MM' -> counter int.

        Returns an empty dict if the file does not exist, is empty, or is
        corrupted.
        """
        path = self._meta_path
        if not path.exists():
            return {}
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                result: Dict[str, int] = {}
                for row in reader:
                    ym = (row.get("year_month") or "").strip()
                    raw_counter = (row.get("counter") or "").strip()
                    if not ym:
                        continue
                    try:
                        result[ym] = int(raw_counter) if raw_counter else 0
                    except ValueError:
                        result[ym] = 0
                return result
        except Exception as exc:
            logger.warning("Could not read meta CSV (%s): %s — starting fresh", path, exc)
            return {}

    def _write_meta(self, meta: Dict[str, int]) -> None:
        """Atomically overwrite loans_meta.csv via write-to-temp + rename.

        Uses pathlib.Path.replace() which maps to os.replace():
        - POSIX: rename(2) syscall — atomic
        - Windows NTFS: MoveFileEx with MOVEFILE_REPLACE_EXISTING — atomic
        If the process crashes before replace(), the original file is intact.
        """
        self._meta_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._meta_path.with_suffix(".tmp")
        rows = [
            {"year_month": ym, "counter": str(order)}
            for ym, order in sorted(meta.items())
        ]
        with tmp.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_META_FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(self._meta_path)
