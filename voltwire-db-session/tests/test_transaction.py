from unittest.mock import MagicMock

import pytest

from voltwire.db.session import DatabaseSessionFactory, RODatabaseSessionFactory, TransactionContext


class TestReadWriteSessionResolution:
    def test_get_session_returns_none_when_nothing_set(self):
        context = TransactionContext()
        assert context.get_session() is None

    def test_set_rw_session_is_returned_by_get_session(self):
        context = TransactionContext()
        session = MagicMock()
        context.set_rw_session(session)
        assert context.get_session() is session

    def test_ro_session_takes_priority_over_rw_session(self):
        context = TransactionContext()
        rw_session = MagicMock()
        ro_session = MagicMock()
        context.set_rw_session(rw_session)
        context.set_ro_session(ro_session)
        assert context.get_session() is ro_session

    def test_reset_ro_session_restores_rw_resolution(self):
        context = TransactionContext()
        rw_session = MagicMock()
        ro_session = MagicMock()
        context.set_rw_session(rw_session)
        token = context.set_ro_session(ro_session)
        context.reset_ro_session(token)
        assert context.get_session() is rw_session

    def test_get_ro_session_returns_none_when_not_set(self):
        context = TransactionContext()
        assert context.get_ro_session() is None


class TestStartTransaction:
    def test_start_transaction_opens_session_from_factory_and_stores_it(self):
        context = TransactionContext()
        session = MagicMock()
        factory = MagicMock(spec=DatabaseSessionFactory)
        factory.get_session.return_value = session

        result = context.start_transaction(factory)

        assert result is session
        assert context.get_session() is session

    def test_on_start_transaction_hook_called_with_factory_before_session_opens(self):
        seen = []
        context = TransactionContext(on_start_transaction=seen.append)
        factory = MagicMock(spec=DatabaseSessionFactory)
        factory.get_session.return_value = MagicMock()

        context.start_transaction(factory)

        assert seen == [factory]

    def test_hook_exception_prevents_session_from_opening(self):
        def guard(_factory):
            raise RuntimeError("wrong database")

        context = TransactionContext(on_start_transaction=guard)
        factory = MagicMock(spec=DatabaseSessionFactory)

        with pytest.raises(RuntimeError, match="wrong database"):
            context.start_transaction(factory)

        factory.get_session.assert_not_called()

    def test_no_hook_by_default(self):
        context = TransactionContext()
        factory = MagicMock(spec=DatabaseSessionFactory)
        factory.get_session.return_value = MagicMock()

        context.start_transaction(factory)  # should not raise


class TestSuspendForIndependentContext:
    def test_clears_and_restores_both_sessions(self):
        context = TransactionContext()
        rw_session = MagicMock()
        ro_session = MagicMock()
        context.set_rw_session(rw_session)
        context.set_ro_session(ro_session)

        with context.suspend_for_independent_context():
            assert context.get_session() is None
            assert context.get_ro_session() is None

        assert context.get_session() is ro_session
        assert context.get_ro_session() is ro_session


class TestLifecycle:
    def test_commit_is_noop_without_rw_session(self):
        context = TransactionContext()
        context.commit()  # should not raise

    def test_commit_delegates_to_session(self):
        context = TransactionContext()
        session = MagicMock()
        context.set_rw_session(session)
        context.commit()
        session.commit.assert_called_once()

    def test_rollback_is_noop_without_rw_session(self):
        context = TransactionContext()
        context.rollback()  # should not raise

    def test_rollback_delegates_to_session(self):
        context = TransactionContext()
        session = MagicMock()
        context.set_rw_session(session)
        context.rollback()
        session.rollback.assert_called_once()

    def test_close_is_noop_without_rw_session(self):
        context = TransactionContext()
        context.close()  # should not raise

    def test_close_delegates_to_session_and_clears_var(self):
        context = TransactionContext()
        session = MagicMock()
        context.set_rw_session(session)
        context.close()
        session.close.assert_called_once()
        assert context.get_session() is None

    def test_ro_session_untouched_by_close(self):
        context = TransactionContext()
        rw_session = MagicMock()
        ro_session = MagicMock()
        context.set_rw_session(rw_session)
        context.set_ro_session(ro_session)
        context.close()
        assert context.get_ro_session() is ro_session


class TestTransactionContextManager:
    def test_commits_on_success(self):
        context = TransactionContext()
        session = MagicMock()
        factory = MagicMock(spec=DatabaseSessionFactory)
        factory.get_session.return_value = session

        with context.transaction(factory):
            pass

        session.commit.assert_called_once()
        session.close.assert_called_once()
        session.rollback.assert_not_called()

    def test_rolls_back_on_exception_and_reraises(self):
        context = TransactionContext()
        session = MagicMock()
        factory = MagicMock(spec=DatabaseSessionFactory)
        factory.get_session.return_value = session

        with pytest.raises(ValueError, match="boom"):
            with context.transaction(factory):
                raise ValueError("boom")

        session.rollback.assert_called_once()
        session.close.assert_called_once()
        session.commit.assert_not_called()

    def test_uses_independent_session_even_if_one_already_set(self):
        context = TransactionContext()
        existing_session = MagicMock()
        context.set_rw_session(existing_session)

        new_session = MagicMock()
        factory = MagicMock(spec=DatabaseSessionFactory)
        factory.get_session.return_value = new_session

        with context.transaction(factory) as session:
            assert session is new_session

        # Original session restored after the independent transaction closes.
        assert context.get_session() is existing_session


class TestReadTransactionContextManager:
    def test_sets_ro_session_for_duration_and_closes_after(self):
        context = TransactionContext()
        session = MagicMock()
        ro_factory = MagicMock(spec=RODatabaseSessionFactory)
        ro_factory.get_session.return_value = session

        with context.read_transaction(ro_factory) as yielded:
            assert yielded is session
            assert context.get_session() is session

        session.close.assert_called_once()
        assert context.get_ro_session() is None

    def test_never_commits_ro_session(self):
        context = TransactionContext()
        session = MagicMock()
        ro_factory = MagicMock(spec=RODatabaseSessionFactory)
        ro_factory.get_session.return_value = session

        with context.read_transaction(ro_factory):
            pass

        session.commit.assert_not_called()
