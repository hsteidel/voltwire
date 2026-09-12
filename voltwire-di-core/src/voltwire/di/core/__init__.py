from dependency_injector import containers, providers

from voltwire.di.core.auto_discovery import auto_discover_components
from voltwire.di.core.container import (
    DependencyContainer,
    dependency_container,
    di,
)
from voltwire.di.core.decorators import (
    analyze_component_dependencies,
    component,
    get_component_registry,
    is_singleton_component,
    settings,
    singleton,
)

__version__ = "0.0.0"

__all__ = [
    "DependencyContainer",
    "analyze_component_dependencies",
    "auto_discover_components",
    "component",
    "containers",
    "dependency_container",
    "di",
    "get_component_registry",
    "is_singleton_component",
    "providers",
    "settings",
    "singleton",
]
