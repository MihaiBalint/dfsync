import pytest
from dfsync.distribution import is_installed_in_editable_mode, get_package_version, update_package


def test_is_installed_in_editable_mode():
    assert is_installed_in_editable_mode("dfsync") is True


def test_is_installed_in_editable_mode_missing_package():
    assert is_installed_in_editable_mode("does-not-exist") is False


def test_is_installed_in_editable_mode_required_and_installed_package():
    assert pytest is not None, "pytest must be installed"
    assert is_installed_in_editable_mode("pytest") is False

    assert is_installed_in_editable_mode("click") is False


def test_update_package():
    tqdm_version = get_package_version("tqdm")

    update_package("tqdm==4.66.2")
    assert get_package_version("tqdm") == "4.66.2"

    update_package("tqdm==4.66.0")
    assert get_package_version("tqdm") == "4.66.0"

    update_package(f"tqdm=={tqdm_version}")
    assert get_package_version("tqdm") == tqdm_version
