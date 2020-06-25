from tempfile import NamedTemporaryFile
from dfsync import __version__

from dfsync.filters import EmacsBufferFilter, UntrackedGitFilesFilter


def test_version():
    assert __version__ == "0.1.0"


def test_emacs_buffer_filter():
    emacs = EmacsBufferFilter()

    assert emacs.is_filtered("test_dfsync.py") is False
    assert emacs.is_filtered("./test_dfsync.py") is False
    assert emacs.is_filtered("./tests/test_dfsync.py") is False
    assert emacs.is_filtered("tests/test_dfsync.py") is False
    assert emacs.is_filtered("/tests/test_dfsync.py") is False

    assert emacs.is_filtered("#test_dfsync.py#") is True
    assert emacs.is_filtered("./#test_dfsync.py#") is True
    assert emacs.is_filtered("./tests/#test_dfsync.py#") is True
    assert emacs.is_filtered("tests/#test_dfsync.py#") is True
    assert emacs.is_filtered("/tests/#test_dfsync.py#") is True

    assert emacs.is_filtered("test_dfsync.py~") is True
    assert emacs.is_filtered("./test_dfsync.py~") is True
    assert emacs.is_filtered("./tests/test_dfsync.py~") is True
    assert emacs.is_filtered("tests/test_dfsync.py~") is True
    assert emacs.is_filtered("/tests/test_dfsync.py~") is True


def test_untracked_git_files_filter():
    git = UntrackedGitFilesFilter()

    assert git.is_filtered(__name__) is False
    assert git.is_filtered("does-not-exist.py") is False

    with NamedTemporaryFile(dir=".") as f:
        assert git.is_filtered(f.name) is True
