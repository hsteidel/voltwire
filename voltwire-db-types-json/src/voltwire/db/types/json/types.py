import logging
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class JSONBList(TypeDecorator, Generic[T]):
    """SQLAlchemy column type for a JSONB array, deserialized as a list of Pydantic models.

    Returns an empty list when the column value is ``NULL``.

    Example::

        class Tag(BaseModel):
            name: str
            colour: str

        class Article(Base):
            tags: Mapped[list[Tag]] = mapped_column(JSONBList(Tag), default=list)
    """

    impl = JSONB

    def __init__(self, item_class: type[T]):
        super().__init__()
        self.item_class = item_class

    def process_result_value(self, value, dialect) -> list[T]:
        if value is None:
            return []
        return [self.item_class.model_validate(item) for item in value]

    def process_bind_param(self, value: list[T] | None, dialect):
        if value is None:
            return None
        return [item.model_dump(mode="json") for item in value]


class JSONBObject(TypeDecorator, Generic[T]):
    """SQLAlchemy column type for a JSONB object, deserialised as a single Pydantic model.

    Returns ``None`` when the column value is ``NULL`` or validation fails (logs an error).

    Example::

        class Address(BaseModel):
            street: str
            city: str

        class User(Base):
            address: Mapped[Address | None] = mapped_column(JSONBObject(Address), nullable=True)
    """

    impl = JSONB
    cache_ok = True

    def __init__(self, item_class: type[T]):
        super().__init__()
        self.item_class = item_class

    def process_result_value(self, value, dialect) -> T | None:
        if value is None:
            return None
        try:
            return self.item_class.model_validate(value)
        except ValidationError as e:
            logger.error(
                "JSONBObject validation failed for %s - returning None to prevent crash: %s",
                self.item_class.__name__,
                e,
            )
            return None

    def process_bind_param(self, value: T | None, dialect):
        if value is None:
            return None
        return value.model_dump(mode="json")
