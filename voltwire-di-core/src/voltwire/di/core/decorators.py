import inspect
import logging
from typing import Callable, Type, TypeVar, Union, get_type_hints

logger = logging.getLogger(__name__)

T = TypeVar("T")

_component_registry: set[Union[Type, Callable]] = set()


def component(cls: Type[T]) -> Type[T]:
    logger.debug(f"Marking {cls.__name__} as component")

    if not _has_valid_constructor(cls):
        raise ValueError(f"@component class {cls.__name__} must have a proper __init__ method")

    _component_registry.add(cls)

    return cls


def singleton(cls: Type[T]) -> Type[T]:
    logger.debug(f"Marking {cls.__name__} as singleton component")

    if not _has_valid_constructor(cls):
        raise ValueError(f"@singleton class {cls.__name__} must have a proper __init__ method")

    cls.__di_singleton__ = True
    _component_registry.add(cls)

    return cls


def is_singleton_component(cls: Type) -> bool:
    return bool(getattr(cls, "__di_singleton__", False))


def get_component_registry() -> set[Union[Type, Callable]]:
    return _component_registry.copy()


def analyze_component_dependencies(cls: Type) -> dict[str, Type]:
    try:
        type_hints = get_type_hints(cls.__init__)
        function_signature = inspect.signature(cls.__init__)

        dependencies = {}
        for name, hint in type_hints.items():
            if name in ("return", "self"):
                continue

            param = function_signature.parameters.get(name)
            if param and param.default is not inspect.Parameter.empty:
                logger.debug(f"Skipping {cls.__name__}.{name} - has default value")
                continue

            dependencies[name] = hint

        logger.debug(f"Analyzed {cls.__name__} dependencies: {list(dependencies.keys())}")

        return dependencies

    except Exception as e:
        raise ValueError(f"Failed to analyze dependencies for {cls.__name__}: {e}") from e


def _has_valid_constructor(cls: Type) -> bool:
    try:
        init_method = getattr(cls, "__init__", None)
        if not init_method or not callable(init_method):
            return False

        signature = inspect.signature(init_method)

        params = list(signature.parameters.keys())
        return len(params) >= 1 and params[0] == "self"

    except Exception:
        return False


def settings(func: Callable) -> Callable:
    registration_type = _extract_return_type(func)

    if not registration_type:
        raise ValueError(f"@settings on {func.__name__} requires a return type annotation")

    func.__di_registration_type__ = registration_type

    _component_registry.add(func)
    logger.debug(f"Marked {func.__name__} as settings provider for {registration_type.__name__}")

    return func


def _extract_return_type(func: Callable) -> Type | None:
    try:
        hints = get_type_hints(func)
        return hints.get("return")
    except Exception as e:
        logger.warning(f"Could not extract return type from {func.__name__}: {e}")
        return None
