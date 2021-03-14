import fnmatch
import os.path
import git.exc
from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileDeletedEvent


def exclude_watchdog_directory_events(event=None, **kwargs):
    event_classes = [FileCreatedEvent, FileDeletedEvent, FileModifiedEvent]
    for event_class in event_classes:
        if isinstance(event, event_class):
            return True
    return False


EMACS_PATTERNS = ["*~", "#*#", ".#*", ".goutputstream-*"]


class LoggingFilter:
    def __init__(self):
        self.ignored_files = set()

    def _ignore(self, src_file_path: str, reason: str = None):
        if src_file_path in self.ignored_files:
            return
        self.ignored_files.add(src_file_path)

        reason = reason or ""
        if len(reason):
            reason = ", {}".format(reason)

        print("Ignored {}{}".format(src_file_path, reason))

    def _unignore(self, src_file_path: str):
        if src_file_path not in self.ignored_files:
            return
        self.ignored_files.remove(src_file_path)

    def is_not_filtered(self, *args, **kwargs):
        return self.is_filtered(*args, **kwargs) is False


class EmacsBufferFilter(LoggingFilter):
    def is_filtered(self, src_file_path: str = None, event=None, **kwargs):
        src_file_path = src_file_path or event.src_path
        if src_file_path is None:
            raise ValueError("A file path or watchdog event is required")

        parent_path, file_name = os.path.split(os.path.expanduser(src_file_path))
        for pattern in EMACS_PATTERNS:
            if fnmatch.fnmatch(file_name, pattern):
                self._ignore(src_file_path, "Emacs buffer backup")
                return True

        return False


class UntrackedGitFilesFilter(LoggingFilter):
    def __init__(self):
        super().__init__()
        self._repo = None
        self._is_repo_initialized = False
        self._modified_untracked_files = set()

    def get_git_repo(self, path: str):
        if self._is_repo_initialized:
            return self._repo

        self._is_repo_initialized = True
        try:
            from git import Repo

            parent_path, _ = os.path.split(os.path.expanduser(path))
            self._repo = Repo(parent_path, search_parent_directories=True)
            print("Using git repo: {}".format(self._repo.working_tree_dir))
        except git.exc.InvalidGitRepositoryError:
            pass
        except ImportError:
            pass

        return self._repo

    def is_filtered(self, src_file_path: str = None, event=None, **kwargs):
        src_file_path = src_file_path or event.src_path
        src_abs_path = os.path.abspath(src_file_path)

        repo = self.get_git_repo(src_file_path)
        if repo is None:
            return False

        if "/.git/" in src_file_path:
            self._ignore(src_file_path, "GIT repo internals")
            return True

        for rel_file_path in repo.untracked_files:
            abs_file_path = os.path.join(repo.working_dir, rel_file_path)
            if src_abs_path == abs_file_path:
                self._ignore(src_file_path, "Untracked GIT file")
                return True
        return False


ALL_FILTERS = [
    exclude_watchdog_directory_events,
    EmacsBufferFilter().is_not_filtered,
    UntrackedGitFilesFilter().is_not_filtered,
]
