from voltwire.di.core import auto_discover_components, di
from tests.sample_components.components import (
    DefaultedService,
    SampleCache,
    SampleCacheConsumer,
    SampleRepository,
    SampleService,
    UnionDepService,
)


def test_auto_discovery_wires_dependency_chain():
    auto_discover_components(base_package="tests.sample_components")

    service = di.provide(SampleService)
    assert isinstance(service.repository, SampleRepository)
    assert service.run() == "repo-value"


def test_auto_discovery_injects_registered_optional_union():
    auto_discover_components(base_package="tests.sample_components")

    service = di.provide(UnionDepService)
    assert service.both_present() is True


def test_auto_discovery_skips_defaulted_parameter():
    auto_discover_components(base_package="tests.sample_components")

    service = di.provide(DefaultedService)
    assert isinstance(service.repository, SampleRepository)
    assert service.flag is False


def test_auto_discovery_registers_singleton_with_shared_instance():
    auto_discover_components(base_package="tests.sample_components")

    first = di.provide(SampleCache)
    second = di.provide(SampleCache)
    assert first is second


def test_auto_discovery_wires_singleton_dependency_chain():
    auto_discover_components(base_package="tests.sample_components")

    consumer = di.provide(SampleCacheConsumer)
    assert isinstance(consumer.cache, SampleCache)
    assert consumer.cache is di.provide(SampleCache)
