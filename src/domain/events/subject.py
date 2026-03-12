from typing import Protocol, TypeVar
from .observer import Observer

T = TypeVar("T")

class Subject(Protocol[T]):
    def subscribe(self, observer: "Observer[T]") -> None:
        ...

    def unsubscribe(self, observer: "Observer[T]") -> None:
        ...

    def notify(self, event: str, data: T) -> None:
        ...