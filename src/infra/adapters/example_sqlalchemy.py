from domain.repositories.example_repository import ExampleRepository
from domain.entities.example import Example


class InMemoryExampleRepository(ExampleRepository):

    def __init__(self):
        self.storage = {}

    def save(self, example: Example):

        self.storage[example.id] = example

    def get_by_id(self, example_id: str):

        return self.storage.get(example_id)