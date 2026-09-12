import importlib
import logging
import pkgutil
import types
from collections.abc import Callable
from dataclasses import dataclass
from typing import Type, get_args, get_origin
from typing import Union as TypingUnion

from dependency_injector import providers

from voltwire.di.core.container import DependencyContainer, dependency_container, di
from voltwire.di.core.decorators import analyze_component_dependencies, get_component_registry, is_singleton_component

logger = logging.getLogger(__name__)


@dataclass
class DependencyAnalysis:
    type: Type
    available: bool
    suggestion: str


@dataclass
class ComponentDependencyAnalysis:
    dependencies: dict[str, DependencyAnalysis]

    def get_missing_dependencies(self) -> dict[str, DependencyAnalysis]:
        return {name: analysis for name, analysis in self.dependencies.items() if not analysis.available}

    def get_available_dependencies(self) -> dict[str, DependencyAnalysis]:
        return {name: analysis for name, analysis in self.dependencies.items() if analysis.available}

    def has_missing_dependencies(self) -> bool:
        return any(not analysis.available for analysis in self.dependencies.values())


def auto_discover_components(
    base_package: str = "src", registrars: list[Callable[[], None]] | None = None
) -> DependencyContainer:
    logger.info(f"Starting auto-discovery of components in package '{base_package}'")

    _import_all_modules(base_package)

    registry = get_component_registry()

    function_components = [item for item in registry if callable(item) and not isinstance(item, type)]
    class_components = [item for item in registry if isinstance(item, type)]

    logger.debug(f"Found {len(function_components)} callable components and {len(class_components)} class components")

    logger.debug(f"Step 1: Registering {len(function_components)} callable components")
    for func in function_components:
        _register_component_function(func)

    if registrars:
        logger.debug(f"Step 2: Calling {len(registrars)} custom registrar(s)")
        for idx, registrar in enumerate(registrars, 1):
            logger.debug(f"Calling registrar {idx}/{len(registrars)}: {registrar.__name__}")
            try:
                registrar()
            except Exception as e:
                logger.error(f"Failed to execute registrar {registrar.__name__}: {e}")
                raise

    logger.debug(f"Step 3: Registering {len(class_components)} class components")

    registered_count = _register_component_classes_with_resolution(class_components)

    logger.info(
        f"Auto-discovery complete: {len(function_components)} functions + {registered_count} classes registered"
    )
    return dependency_container()


def _import_all_modules(package_name: str) -> None:
    try:
        package = importlib.import_module(package_name)
        package_path = getattr(package, "__path__", None)

        if package_path is None:
            return

        for _, module_name, _ in pkgutil.walk_packages(package_path, package_name + "."):
            try:
                importlib.import_module(module_name)
            except Exception as e:
                logger.debug(f"Could not import module {module_name}: {e}")
                continue

    except Exception as e:
        logger.warning(f"Could not scan package {package_name}: {e}")


def _register_component(component_cls: Type) -> None:
    is_singleton = is_singleton_component(component_cls)
    dependencies = analyze_component_dependencies(component_cls)

    if not dependencies:
        if is_singleton:
            di.register_singleton(component_cls)
        else:
            di.register_factory(component_cls)
        return

    for param_name, param_type in dependencies.items():
        base_type, is_optional = _unwrap_union_non_none(param_type)
        if is_optional and not di.provider_exists(base_type):
            continue
        if not di.provider_exists(base_type):
            available_types = _get_registered_types()
            available_names = [_get_type_name(cls) for cls in available_types]
            raise ValueError(
                f"Cannot resolve dependency '{param_name}: {_get_type_name(param_type)}' for {component_cls.__name__}. "
                f"Available types: {available_names}"
            )

    def lazy_factory():
        container = dependency_container()
        resolved_deps = {}
        for item_name, item_type in dependencies.items():
            base_type, is_optional = _unwrap_union_non_none(item_type)
            if is_optional and not di.provider_exists(base_type):
                continue
            resolved_deps[item_name] = container.provide(base_type)
        return component_cls(**resolved_deps)

    provider_cls = providers.Singleton if is_singleton else providers.Callable
    di.register(component_cls, provider_cls(lazy_factory))


def _unwrap_union_non_none(tp: type) -> tuple[type, bool]:
    origin = None
    try:
        origin = get_origin(tp)
    except Exception:
        pass
    if origin in (types.UnionType, TypingUnion):
        args = get_args(tp)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0], True
    return tp, False


def _get_registered_types() -> set[Type]:
    try:
        container = dependency_container()
        return set(container.get_registry_keys())
    except Exception:
        return set()


def _get_type_name(param_type: type) -> str:
    if isinstance(param_type, types.UnionType):
        args = get_args(param_type)
        arg_names = [_get_type_name(arg) for arg in args]
        return " | ".join(arg_names)
    elif hasattr(param_type, "__name__"):
        return param_type.__name__
    elif hasattr(param_type, "_name"):
        return param_type._name  # noqa: SLF001
    else:
        return str(param_type)


def _register_component_function(func) -> None:
    registration_type = getattr(func, "__di_registration_type__", None)
    if not registration_type:
        raise ValueError(f"Component function {func.__name__} missing __di_registration_type__ metadata")

    try:
        component_instance = func()
        di.register(registration_type, providers.Object(component_instance))

        logger.debug(f"Registered settings: {registration_type.__name__} from {func.__name__}()")
    except Exception as e:
        logger.error(f"Failed to register settings from {func.__name__}: {e}")
        raise


def _register_component_classes_with_resolution(class_components: list[Type]) -> int:
    remaining_components = set(class_components)
    registered_count = 0
    pass_number = 1
    max_passes = len(class_components) + 1

    while remaining_components and pass_number <= max_passes:
        logger.debug(f"Registration pass {pass_number}: {len(remaining_components)} components remaining")

        registered_this_pass = []

        for component_cls in list(remaining_components):
            try:
                _register_component(component_cls)
                registered_this_pass.append(component_cls)
                registered_count += 1
                logger.debug(f"Successfully registered component: {component_cls.__name__}")
            except Exception as e:
                logger.debug(f"Pass {pass_number}: {component_cls.__name__} not ready: {e}")
                continue

        for component_cls in registered_this_pass:
            remaining_components.remove(component_cls)

        if not registered_this_pass:
            logger.debug(f"No progress in pass {pass_number}, stopping registration")
            break

        pass_number += 1

    if remaining_components:
        _report_unregistered_components(remaining_components)

    return registered_count


def _report_unregistered_components(unregistered: set[Type]) -> None:
    logger.warning(f"Could not register {len(unregistered)} components due to missing dependencies:")
    logger.warning("")

    for component_cls in unregistered:
        analysis = _analyze_missing_dependencies(component_cls)

        if not analysis.dependencies:
            logger.warning(f"  - {component_cls.__name__} (could not analyze dependencies)")
            continue

        total_count = len(analysis.dependencies)

        logger.warning(f"  - {component_cls.__name__} requires {total_count} dependencies:")

        for param_name, dep_info in analysis.get_available_dependencies().items():
            logger.warning(f"    ✓ {param_name}: {_get_type_name(dep_info.type)} (available)")

        for param_name, dep_info in analysis.get_missing_dependencies().items():
            suggestion = f" - {dep_info.suggestion}" if dep_info.suggestion else ""
            logger.warning(f"    ✗ {param_name}: {_get_type_name(dep_info.type)} (not registered{suggestion})")

        logger.warning("")

    logger.warning("To fix these issues:")
    logger.warning("  1. Add @component decorator to missing service/repository classes")
    logger.warning("  2. Or register missing dependencies manually as singletons before discovery")
    logger.warning("  3. Ensure all imported dependencies are accessible")


def _analyze_missing_dependencies(component_cls: Type) -> ComponentDependencyAnalysis:
    try:
        dependencies = analyze_component_dependencies(component_cls)
        registered_types = _get_registered_types()

        analysis = {}
        for param_name, param_type in dependencies.items():
            is_available = param_type in registered_types

            suggestion = ""
            if not is_available:
                type_name = _get_type_name(param_type)
                suggestion = f"Register {type_name} with @component decorator or manually as a singleton"

            analysis[param_name] = DependencyAnalysis(type=param_type, available=is_available, suggestion=suggestion)

        return ComponentDependencyAnalysis(dependencies=analysis)

    except Exception as e:
        logger.error(f"Failed to analyze dependencies for {component_cls.__name__}: {e}")
        return ComponentDependencyAnalysis(dependencies={})
