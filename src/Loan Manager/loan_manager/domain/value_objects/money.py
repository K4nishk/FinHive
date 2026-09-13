from dataclasses import dataclass

@dataclass(frozen=True)
class Money:
    amount: int  # INR, non-negative integer

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError(f"Amount must be non-negative, got {self.amount}")

    def __int__(self) -> int:
        return self.amount
