from domain.entities.example import Example
from domain.repositories.example_repository import ExampleRepository
from domain.events.event_broker import EventBroker


class CreateExample:

    def __init__(
        self,
        repository: ExampleRepository,
        event_broker: EventBroker
    ):
        self.repository = repository
        self.event_broker = event_broker

    def execute(self, id: str, name: str):

        example = Example(id=id, name=name)

        self.repository.save(example)

        self.event_broker.publish(
            "example_created",
            {"id": id}
        )

        return example