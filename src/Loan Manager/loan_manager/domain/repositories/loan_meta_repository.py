from abc import ABC, abstractmethod
from typing import Optional


class ILoanMetaRepository(ABC):
    @abstractmethod
    def get_last_order(self, year_month: str) -> Optional[int]: ...

    @abstractmethod
    def set_last_order(self, year_month: str, order: int) -> None: ...
