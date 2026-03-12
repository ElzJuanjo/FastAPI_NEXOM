from __future__ import annotations

from typing import Generic, TypeVar, Set
from .observer import Observer

T = TypeVar("T")


class EventBroker(Generic[T]):

    _instance: EventBroker | None = None

    def __init__(self) -> None:
        self._observers: Set[Observer[T]] = set()

    @classmethod
    def get_instance(cls) -> EventBroker:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def subscribe(self, observer: Observer[T]) -> None:
        self._observers.add(observer)

    def unsubscribe(self, observer: Observer[T]) -> None:
        self._observers.discard(observer)

    def notify(self, event: str, data: T) -> None:
        for observer in self._observers:
            observer.update(event, data)