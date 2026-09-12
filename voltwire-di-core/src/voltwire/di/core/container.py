import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Type, TypeVar

from dependency_injector import containers, providers

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(eq=False, repr=False)
class DependencyContainer(containers.DynamicContainer):
    _type_registry: dict[Type, str] = field(default_factory=dict)
    _core_providers: list[Callable[[], None]] = field(default_factory=list)
    _core_providers_initialized: bool = False
    _init_lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        super().__init__()

    def register(self, cls: Type[T], provider: providers.Provider):
        name = f"_type_{cls.__module__}.{cls.__qualname__}"
        self.set_provider(name, provider)
        self._type_registry[cls] = name
        logger.debug(f"Registered provider for {cls}")

    def register_factory(self, cls: Type[T], **kwargs):
        factory = providers.Factory(cls, **kwargs)
        self.register(cls, factory)

    def register_singleton(self, cls: Type[T], **kwargs):
        singleton = providers.Singleton(cls, **kwargs)
        self.register(cls, singleton)

    def provide(self, cls: Type[T]) -> T:
        name = self._type_registry.get(cls)
        if not name:
            raise KeyError(f"No provider for {cls}")
        logger.debug(f"Providing {cls}")
        return self.providers[name]()

    def get_provider(self, cls: Type[T]) -> providers.Provider:
        name = self._type_registry.get(cls)
        if not name:
            raise KeyError(f"No provider for {cls}")
        return self.providers[name]

    def get_registry_keys(self):
        return self._type_registry.keys()

    def get_registered_type_by_name(self, class_name: str) -> type | None:
        for registered_class in self.get_registry_keys():
            if registered_class.__name__ == class_name:
                return registered_class
        return None

    def register_core_provider(self, registrar: Callable[[], None]) -> None:
        self._core_providers.append(registrar)

    def ensure_core_providers(self) -> None:
        with self._init_lock:
            if self._core_providers_initialized:
                return

            for registrar in self._core_providers:
                registrar()

            self._core_providers_initialized = True


logger.debug("Creating dependency container")
__container = DependencyContainer()
logger.debug("Dependency container created")


def dependency_container() -> DependencyContainer:
    return __container


class _DI:
    """Facade over the module-level dependency container, addressed as `di.<verb>(...)`."""

    def register(self, cls: Type[T], provider: providers.Provider) -> None:
        dependency_container().register(cls, provider)

    def register_factory(self, cls: Type[T], **kwargs) -> None:
        dependency_container().register_factory(cls, **kwargs)

    def register_singleton(self, cls: Type[T], **kwargs) -> None:
        dependency_container().register_singleton(cls, **kwargs)

    def provide(self, cls: Type[T]) -> T:
        self.ensure_core_providers()
        try:
            return dependency_container().provide(cls)
        except KeyError as e:
            logger.error(f"No provider for {cls}")
            raise e

    def get_provider(self, cls: Type[T]) -> providers.Provider:
        self.ensure_core_providers()
        return dependency_container().get_provider(cls)

    def provider_exists(self, cls: Type[T]) -> bool:
        self.ensure_core_providers()
        return cls in dependency_container().get_registry_keys()

    def register_core_provider(self, registrar: Callable[[], None]) -> None:
        dependency_container().register_core_provider(registrar)

    def ensure_core_providers(self) -> None:
        dependency_container().ensure_core_providers()


di = _DI()
