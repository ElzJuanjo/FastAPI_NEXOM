from infra.adapters.example_sqlalchemy import InMemoryExampleRepository
from domain.events.event_broker import EventBroker
from app.use_cases.example_create import CreateExample


def get_example_repository():

    return InMemoryExampleRepository()


def get_event_broker():

    return EventBroker()


def get_create_example_use_case():

    repository = get_example_repository()

    event_broker = get_event_broker()

    return CreateExample(repository, event_broker)