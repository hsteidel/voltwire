import pytest
from dependency_injector import providers

from voltwire.di.core.container import DependencyContainer


class Widget:
    def __init__(self, label: str = "w"):
        self.label = label


class Gadget:
    def __init__(self):
        pass


def test_register_factory_provides_new_instances():
    container = DependencyContainer()
    container.register_factory(Widget)
    first = container.provide(Widget)
    second = container.provide(Widget)
    assert isinstance(first, Widget)
    assert first is not second


def test_register_singleton_provides_same_instance():
    container = DependencyContainer()
    container.register_singleton(Gadget)
    assert container.provide(Gadget) is container.provide(Gadget)


def test_register_raw_provider():
    container = DependencyContainer()
    instance = Gadget()
    container.register(Gadget, providers.Object(instance))
    assert container.provide(Gadget) is instance


def test_provide_unknown_type_raises_keyerror():
    container = DependencyContainer()
    with pytest.raises(KeyError):
        container.provide(Widget)


def test_get_registered_type_by_name():
    container = DependencyContainer()
    container.register_factory(Widget)
    assert container.get_registered_type_by_name("Widget") is Widget
    assert container.get_registered_type_by_name("Missing") is None


def test_core_providers_run_in_order_exactly_once():
    container = DependencyContainer()
    calls = []
    container.register_core_provider(lambda: calls.append("a"))
    container.register_core_provider(lambda: calls.append("b"))

    container.ensure_core_providers()
    container.ensure_core_providers()

    assert calls == ["a", "b"]


def test_core_provider_can_register_into_container():
    container = DependencyContainer()

    def registrar():
        container.register_singleton(Gadget)

    container.register_core_provider(registrar)
    container.ensure_core_providers()

    assert isinstance(container.provide(Gadget), Gadget)
