from dfsync.lib import ControlledThreadedOperation, ThreadedOperationsManager, dsn_pack, dsn_unpack


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


def test_dsn_pack_unpack():
    # Test basic packing and unpacking
    original_dsn = "test_dsn_string"
    packed = dsn_pack(original_dsn)
    unpacked = dsn_unpack(packed)
    assert unpacked == original_dsn

    # Test with empty string
    assert dsn_unpack(dsn_pack("")) == ""

    # Test with longer string
    long_dsn = "https://very.long.dsn.string.with.special/characters?key=value&other=123"
    assert dsn_unpack(dsn_pack(long_dsn)) == long_dsn

    # Test that packed value is different from original
    assert dsn_pack("test") != "test"

    # Test that consecutive packs produce same result
    assert dsn_pack("test") == dsn_pack("test")
