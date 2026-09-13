from __future__ import annotations


class ReferenceIdService:
    @staticmethod
    def next_id(year: int, month: int, last_order: int | None) -> str:
        """Generate next reference ID. last_order=None means counter starts at 1."""
        order = 1 if last_order is None else last_order + 1
        return f"{year:04d}_{month:02d}_{ReferenceIdService.format_order(order)}"

    @staticmethod
    def parse(ref_id: str) -> tuple[int, int, int]:
        """Parse reference ID into (year, month, order)."""
        parts = ref_id.split("_")
        if len(parts) != 3:
            raise ValueError(f"Invalid reference_id format: {ref_id!r}")
        return int(parts[0]), int(parts[1]), int(parts[2])

    @staticmethod
    def format_order(order: int) -> str:
        return f"{order:03d}" if order < 1000 else str(order)

    @staticmethod
    def year_month_key(year: int, month: int) -> str:
        return f"{year:04d}_{month:02d}"
