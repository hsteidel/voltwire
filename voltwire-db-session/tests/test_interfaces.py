"""
Verifies the ORM-agnostic facade: TransactionContext and the interfaces module never
import sqlalchemy, and a plain non-SQLAlchemy object satisfies the interfaces
structurally.
"""

from pathlib import Path
from unittest.mock import MagicMock

import voltwire.db.session.interfaces as interfaces_module
import voltwire.db.session.transaction as transaction_module
from voltwire.db.session import DatabaseSessionFactory, RODatabaseSessionFactory, Session, TransactionContext
from voltwire.db.session.backends.sqlalchemy import SqlAlchemyDatabaseSessionFactory


class FakeOrmSession:
    """A stand-in for some other ORM's session — no sqlalchemy involved."""

    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class FakeOrmSessionFactory:
    def __init__(self, session: FakeOrmSession):
        self._session = session

    def get_session(self) -> FakeOrmSession:
        return self._session

    def get_engine(self):
        return None

    def close(self) -> None:
        pass


def _source_has_no_sqlalchemy_import(module) -> bool:
    source = Path(module.__file__).read_text()
    return all(
        "sqlalchemy" not in line.lower()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    )


class TestNoSqlAlchemyCoupling:
    def test_transaction_module_does_not_import_sqlalchemy(self):
        assert _source_has_no_sqlalchemy_import(transaction_module)

    def test_interfaces_module_does_not_import_sqlalchemy(self):
        assert _source_has_no_sqlalchemy_import(interfaces_module)


class TestStructuralConformance:
    def test_sqlalchemy_factory_satisfies_interface_without_subclassing(self):
        assert DatabaseSessionFactory not in SqlAlchemyDatabaseSessionFactory.__mro__

    def test_fake_orm_factory_satisfies_database_session_factory_protocol(self):
        factory = FakeOrmSessionFactory(FakeOrmSession())
        assert isinstance(factory, DatabaseSessionFactory)
        assert isinstance(factory, RODatabaseSessionFactory)

    def test_fake_orm_session_satisfies_session_protocol(self):
        assert isinstance(FakeOrmSession(), Session)

    def test_plain_object_missing_methods_does_not_satisfy_session_protocol(self):
        assert not isinstance(object(), Session)


class TestTransactionContextWorksWithNonSqlAlchemySession:
    def test_transaction_commits_a_fake_orm_session(self):
        context = TransactionContext()
        fake_session = FakeOrmSession()
        factory = FakeOrmSessionFactory(fake_session)

        with context.transaction(factory) as session:
            assert session is fake_session

        assert fake_session.committed is True
        assert fake_session.closed is True

    def test_transaction_rolls_back_a_fake_orm_session_on_exception(self):
        context = TransactionContext()
        fake_session = FakeOrmSession()
        factory = FakeOrmSessionFactory(fake_session)

        try:
            with context.transaction(factory):
                raise ValueError("boom")
        except ValueError:
            pass

        assert fake_session.rolled_back is True
        assert fake_session.closed is True

    def test_read_transaction_never_commits_a_fake_orm_session(self):
        context = TransactionContext()
        fake_session = FakeOrmSession()
        ro_factory = FakeOrmSessionFactory(fake_session)

        with context.read_transaction(ro_factory) as session:
            assert session is fake_session

        assert fake_session.committed is False
        assert fake_session.closed is True

    def test_generic_mock_session_still_works(self):
        # Sanity check: existing MagicMock-based usage from other tests is unaffected.
        context = TransactionContext()
        session = MagicMock()
        context.set_rw_session(session)
        context.commit()
        session.commit.assert_called_once()
