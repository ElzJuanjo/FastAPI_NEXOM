from typing import Protocol
from domain.entities.example import Example


class ExampleRepository(Protocol):

    def save(self, example: Example) -> None:
        ...

    def get_by_id(self, example_id: str) -> Example | None:
        ...