import black
import fnmatch
import os.path
import git.exc
import subprocess
from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileDeletedEvent


def exclude_watchdog_directory_events(event=None, **kwargs):
    event_classes = [FileCreatedEvent, FileDeletedEvent, FileModifiedEvent]
    for event_class in event_classes:
        if isinstance(event, event_class):
            return True
    return False


EMACS_PATTERNS = ["*~", "#*#", ".#*", ".goutputstream-*", "*_flymake.py"]
PYTHON_PATTERNS = ["*.py"]


def echo(msg):
    print(f"{msg}")


class LoggingFilter:
    def __init__(self):
        self.ignored_files = set()

    def _ignore(self, src_file_path: str, reason: str = None):
        if src_file_path in self.ignored_files:
            return
        self.ignored_files.add(src_file_path)

        reason = reason or ""
        if len(reason):
            reason = f", {reason}"

        echo(f"Ignored {src_file_path}{reason}")

    def _unignore(self, src_file_path: str):
        if src_file_path not in self.ignored_files:
            return
        self.ignored_files.remove(src_file_path)

    def is_not_filtered(self, *args, **kwargs):
        return self.is_filtered(*args, **kwargs) is False


class UserConfigFilter(LoggingFilter):
    def __init__(self, ignored_patterns):
        super().__init__()
        self._ignored_patterns = ignored_patterns
        self._ignore_message = "ignoring, matches pattern from ignore_files config"
        for pattern in ignored_patterns:
            if "*" not in pattern:
                self.ignored_files.add(pattern)

    def is_filtered(self, src_file_path: str = None, event=None, **kwargs):
        src_file_path = src_file_path or event.src_path
        if src_file_path is None:
            raise ValueError("A file path or watchdog event is required")

        parent_path, file_name = os.path.split(os.path.expanduser(src_file_path))
        for pattern in self._ignored_patterns:
            if fnmatch.fnmatch(file_name, pattern):
                self._ignore(src_file_path, self._ignore_message)
                return True

        return False


class EmacsBufferFilter(UserConfigFilter):
    def __init__(self):
        super().__init__(EMACS_PATTERNS)
        self._ignore_message = "Emacs buffer backup"


class PythonBlackFilter(LoggingFilter):
    def __init__(self):
        super().__init__()

    def is_filtered(self, src_file_path: str = None, event=None, **kwargs):
        src_file_path = src_file_path or event.src_path
        if src_file_path is None:
            raise ValueError("A file path or watchdog event is required")

        parent_path, file_name = os.path.split(os.path.expanduser(src_file_path))
        for pattern in PYTHON_PATTERNS:
            if fnmatch.fnmatch(file_name, pattern):
                return self._black_check(src_file_path)
        return False

    def _black_check(self, src_file_path):
        try:
            with open(src_file_path, "r") as f:
                contents = f.read()
                black.format_file_contents(contents, fast=False, mode=black.FileMode())
            return False

        except (FileNotFoundError, PermissionError, black.report.NothingChanged) as e:
            return False

        except Exception as e:
            message = str(e) or type(e).__name__
            echo(f"Rejected {src_file_path}, {message}")
            return True


class UntrackedGitFilesFilter(LoggingFilter):
    def __init__(self):
        super().__init__()
        self._repos = {}
        self._is_repo_initialized = {}
        self._untracked_and_ignored_files = {}
        self._should_filter_untracked_files = True

    def set_should_filter_untracked_files(self, should_filter_untracked_files: bool = True):
        self._should_filter_untracked_files = should_filter_untracked_files

    def get_untracked_and_ignored_files(self):
        flat_files = []
        for fn in self._untracked_and_ignored_files.values():
            flat_files.extend(fn)
        return flat_files

    def _get_existing_parent(self, path):
        exists = False
        parent_path = None
        while not exists:
            parent_path, _ = os.path.split(os.path.expanduser(path))
            exists = os.path.isdir(parent_path) and os.path.exists(parent_path)
            if len(parent_path) == 0:
                return None
        return parent_path

    def get_git_repo(self, path: str):
        # BUG: path isn't the repo path it's the path of any of the modifiable files in the repo
        for repo_dir, repo in self._repos.items():
            if path_is_parent(repo_dir, path):
                return repo

        repo = None
        try:
            from git import Repo

            parent_path = self._get_existing_parent(path)
            if parent_path is not None:
                repo = Repo(parent_path, search_parent_directories=True)
                self._repos[repo.working_tree_dir] = repo
                self._is_repo_initialized[repo.working_tree_dir] = True
                echo("Using git repo: {}".format(repo.working_tree_dir))
        except git.exc.InvalidGitRepositoryError:
            pass
        except ImportError:
            pass

        return repo

    def load_ignored_files(self, cwd):
        files = subprocess.check_output("git ls-files --exclude-standard -oi --directory".split(" "), cwd=cwd)
        files = files.decode("utf8")

        file_list = [f.strip() for f in files.split("\n") if len(f.strip()) > 0]
        self._untracked_and_ignored_files[cwd] = file_list

    def is_filtered(self, src_file_path: str = None, event=None, **kwargs):
        src_file_path = src_file_path or event.src_path
        src_abs_path = os.path.abspath(src_file_path)

        repo = self.get_git_repo(src_file_path)
        if repo is None:
            return False
        self.load_ignored_files(repo.working_tree_dir)

        if repo.ignored(src_abs_path):
            self._ignore(src_file_path, "file is in .gitignore")
            return True

        if "/.git/" in src_file_path:
            self._ignore(src_file_path, "GIT repo internals")
            return True

        if self._should_filter_untracked_files and self._is_untracked_file(repo, src_abs_path):
            self._ignore(src_file_path, "Untracked GIT file")
            return True

        return False

    def _is_untracked_file(self, repo, src_abs_path):
        return any(
            src_abs_path == os.path.join(repo.working_dir, rel_file_path) for rel_file_path in repo.untracked_files
        )


USER_FILTERS = [EmacsBufferFilter(), PythonBlackFilter()]
GIT_FILTER = UntrackedGitFilesFilter()
ALL_FILTERS = [
    exclude_watchdog_directory_events,
    *[f.is_not_filtered for f in USER_FILTERS],
    GIT_FILTER.is_not_filtered,
]


def list_files_to_ignore():
    result = set(GIT_FILTER.get_untracked_and_ignored_files())
    for editor_filter in USER_FILTERS:
        result = {*result, *editor_filter.ignored_files}
    return result


def path_is_parent(parent_path, child_path):
    parent_path = os.path.abspath(parent_path)
    child_path = os.path.abspath(child_path)

    return os.path.commonpath([parent_path]) == os.path.commonpath([parent_path, child_path])


def add_user_filter(f: LoggingFilter):
    if f is None:
        raise ValueError("Expecting non-null user filter")
    USER_FILTERS.append(f)
    ALL_FILTERS.append(f.is_not_filtered)


def add_user_ignored_patterns_filter(patterns: [str]):
    add_user_filter(UserConfigFilter(patterns))


def set_ignore_untracked_files(should_ignore_untracked_files: bool):
    GIT_FILTER.set_should_filter_untracked_files(should_ignore_untracked_files)
