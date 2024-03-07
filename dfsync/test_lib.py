import pytest
from dfsync.lib import ControlledThreadedOperation, ThreadedOperationsManager


def test_threaded_operations_manager():
    manager = ThreadedOperationsManager()
    assert len(manager.threads) == 0

    operation = ControlledThreadedOperation()
    manager.register_threaded_operation(operation)
    assert len(manager.threads) == 1

    manager.stop()
    assert operation.is_completed


def test_controlled_threaded_operation():
    operation = ControlledThreadedOperation()
    assert not operation.is_running
    assert operation.is_completed

    operation.start()
    assert operation.is_running
    assert not operation.is_completed

    operation.stop()
    assert not operation.is_running
    assert operation.is_completed
