<img src="https://raw.githubusercontent.com/hsteidel/voltwire/main/assets/icons/db-types-json.svg" alt="" width="56" height="56" align="left">

# voltwire-db-types-json

Custom SQLAlchemy column types for PostgreSQL JSONB columns, backed by Pydantic models. Handles serialisation, deserialisation, and validation transparently — your columns read and write Pydantic model instances directly.

## Installation

```bash
pip install voltwire-db-types-json
# or with Poetry:
poetry add voltwire-db-types-json
```

## Types

### `JSONBList[T]` — JSONB array as a list of Pydantic models

Returns an empty list when the column value is `NULL`.

```python
from pydantic import BaseModel
from sqlalchemy.orm import mapped_column, Mapped
from voltwire.db.types.json import JSONBList

class Tag(BaseModel):
    name: str
    colour: str

class Article(Base):
    __tablename__ = "articles"
    tags: Mapped[list[Tag]] = mapped_column(JSONBList(Tag), default=list)
```

### `JSONBObject[T]` — JSONB object as a single Pydantic model

Returns `None` when the column value is `NULL` or validation fails (logs an error, does not raise).

```python
from voltwire.db.types.json import JSONBObject

class Address(BaseModel):
    street: str
    city: str

class User(Base):
    __tablename__ = "users"
    address: Mapped[Address | None] = mapped_column(JSONBObject(Address), nullable=True)
```
