from pydantic import BaseModel

from voltwire.db.types.json import JSONBList, JSONBObject


# --- Fixtures ---

class Tag(BaseModel):
    name: str
    colour: str


class Address(BaseModel):
    street: str
    city: str


# --- JSONBList ---

class TestJSONBList:
    def test_process_result_value_deserialises_list(self):
        col = JSONBList(Tag)
        result = col.process_result_value([{"name": "python", "colour": "blue"}], dialect=None)
        assert result == [Tag(name="python", colour="blue")]

    def test_process_result_value_returns_empty_list_for_null(self):
        col = JSONBList(Tag)
        assert col.process_result_value(None, dialect=None) == []

    def test_process_bind_param_serialises_list(self):
        col = JSONBList(Tag)
        result = col.process_bind_param([Tag(name="python", colour="blue")], dialect=None)
        assert result == [{"name": "python", "colour": "blue"}]

    def test_process_bind_param_returns_none_for_null(self):
        col = JSONBList(Tag)
        assert col.process_bind_param(None, dialect=None) is None


# --- JSONBObject ---

class TestJSONBObject:
    def test_process_result_value_deserialises_object(self):
        col = JSONBObject(Address)
        result = col.process_result_value({"street": "1 Main St", "city": "Springfield"}, dialect=None)
        assert result == Address(street="1 Main St", city="Springfield")

    def test_process_result_value_returns_none_for_null(self):
        col = JSONBObject(Address)
        assert col.process_result_value(None, dialect=None) is None

    def test_process_result_value_returns_none_on_validation_error(self):
        col = JSONBObject(Address)
        result = col.process_result_value({"bad": "data"}, dialect=None)
        assert result is None

    def test_process_bind_param_serialises_object(self):
        col = JSONBObject(Address)
        result = col.process_bind_param(Address(street="1 Main St", city="Springfield"), dialect=None)
        assert result == {"street": "1 Main St", "city": "Springfield"}

    def test_process_bind_param_returns_none_for_null(self):
        col = JSONBObject(Address)
        assert col.process_bind_param(None, dialect=None) is None
