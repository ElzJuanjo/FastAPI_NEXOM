from typing import Protocol, TypeVar

T = TypeVar("T")

class Observer(Protocol[T]):
    def update(self, event: str, data: T) -> None:
        ...