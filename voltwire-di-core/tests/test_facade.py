from voltwire.di.core import containers, providers
from voltwire.di.core.container import DependencyContainer


def test_providers_facade_exposes_provider_types():
    container = DependencyContainer()

    class Thing:
        def __init__(self):
            pass

    container.register(Thing, providers.Object(Thing()))
    assert isinstance(container.provide(Thing), Thing)


def test_containers_facade_is_dependency_injector_module():
    assert hasattr(containers, "DynamicContainer")
