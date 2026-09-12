from voltwire.di.core import component, singleton


@component
class SampleRepository:
    def __init__(self):
        pass

    def value(self) -> str:
        return "repo-value"


@component
class SampleService:
    def __init__(self, repository: SampleRepository):
        self.repository = repository

    def run(self) -> str:
        return self.repository.value()


@component
class UnionDepService:
    def __init__(self, repository: SampleRepository, optional_repo: SampleRepository | None):
        self.repository = repository
        self.optional_repo = optional_repo

    def both_present(self) -> bool:
        return self.repository is not None and self.optional_repo is not None


@component
class DefaultedService:
    def __init__(self, repository: SampleRepository, flag: bool = False):
        self.repository = repository
        self.flag = flag


@singleton
class SampleCache:
    def __init__(self):
        pass


@singleton
class SampleCacheConsumer:
    def __init__(self, cache: SampleCache):
        self.cache = cache
