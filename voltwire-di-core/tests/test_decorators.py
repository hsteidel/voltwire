import pytest

from voltwire.di.core.decorators import (
    analyze_component_dependencies,
    component,
    get_component_registry,
    is_singleton_component,
    settings,
    singleton,
)


class Alpha:
    def __init__(self):
        pass


class Beta:
    def __init__(self, alpha: Alpha, name: str = "x"):
        self.alpha = alpha
        self.name = name


def test_component_returns_class_and_registers():
    returned = component(Alpha)
    assert returned is Alpha
    assert Alpha in get_component_registry()


def test_component_rejects_invalid_constructor():
    class Bad:
        pass

    Bad.__init__ = lambda: None

    with pytest.raises(ValueError):
        component(Bad)


def test_analyze_includes_required_and_skips_defaulted():
    assert analyze_component_dependencies(Beta) == {"alpha": Alpha}


def test_analyze_empty_for_no_dependency_constructor():
    assert analyze_component_dependencies(Alpha) == {}


def test_settings_sets_registration_type_and_registers():
    @settings
    def make_alpha() -> Alpha:
        return Alpha()

    assert make_alpha.__di_registration_type__ is Alpha
    assert make_alpha in get_component_registry()


def test_settings_requires_return_annotation():
    def no_annotation():
        return 1

    with pytest.raises(ValueError):
        settings(no_annotation)


def test_singleton_returns_class_and_registers():
    returned = singleton(Alpha)
    assert returned is Alpha
    assert Alpha in get_component_registry()
    assert is_singleton_component(Alpha) is True


def test_singleton_rejects_invalid_constructor():
    class Bad:
        pass

    Bad.__init__ = lambda: None

    with pytest.raises(ValueError):
        singleton(Bad)


def test_is_singleton_component_false_for_plain_component():
    class Plain:
        def __init__(self):
            pass

    component(Plain)
    assert is_singleton_component(Plain) is False
