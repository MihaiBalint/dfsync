import click
import os
import os.path
import sys
import time
import logging
import queue

from click_default_group import DefaultGroup
from contextlib import contextmanager
from functools import partial
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from dfsync.backends import rsync_backend, kube_backend
from dfsync.distribution import get_installed_version, get_latest_version, is_older_version, AsyncVersionChecker
from dfsync.filters import add_user_ignored_patterns_filter, ALL_FILTERS
from dfsync.config import read_config
from dfsync.char_ui import KeyController
from dfsync.kube_credentials import contextualize_kube_credentials, update_local_kube_config
from dfsync.lib import ControlledThreadedOperation, thread_manager

logging.basicConfig(level=logging.WARN)

BACKENDS = {
    # File sync backends
    "file-rsync": rsync_backend,
    "kube-rsync": kube_backend,
}


class IgnoreEvent(Exception):
    pass


class RelatedLocationsError(ValueError):
    pass


class FileChangedEventHandler(ControlledThreadedOperation, FileSystemEventHandler):
    def __init__(
        self,
        backend: str = "log",
        watched_dir: str = ".",
        all_watched_dirs: list = None,
        input_controller: KeyController = None,
        **kwargs,
    ):
        super().__init__()
        self.filters = [*ALL_FILTERS]

        self.backend = backend
        self.backend_options = kwargs
        self.raised_exception = False
        self.watched_dir = watched_dir
        self.abs_watched_dir = os.path.abspath(watched_dir)
        self.input_controller = input_controller
        self.events = queue.Queue(maxsize=10000)
        self.full_sync_threashold = 3
        self.all_watched_dirs = all_watched_dirs if all_watched_dirs is not None else [watched_dir]

    def _log_backend(self, event):
        logging.info(event)

    @contextmanager
    def _input_lock(self):
        if self.input_controller is None:
            yield self
        else:
            with self.input_controller.getch_lock():
                yield self

    @contextmanager
    def terminal_lock(self):
        try:
            with self._input_lock():
                yield self
        except IgnoreEvent:
            pass
        except:
            self.raised_exception = True
            raise

    def _sync(self, event):
        # It seems like in some contexts, event.src_path will be an absolute path
        # and in some other contexts, it will be a relative path

        src_file_path = self._get_path_relative_to_watched_dir(event.src_path, self.abs_watched_dir)
        self.backend.sync(
            src_file_path=src_file_path,
            event=event,
            watched_dir=self.abs_watched_dir,
            **self.backend_options,
        )

    def _get_path_relative_to_watched_dir(self, path, parent_path):
        try:
            abs_path = os.path.abspath(path)
            common = os.path.commonpath([parent_path, abs_path])

            rel_watched = os.path.relpath(parent_path, start=common)
            rel_path = os.path.relpath(abs_path, start=common)

            # Sanity checks
            if rel_watched not in ["", ".", "./"]:
                raise IgnoreEvent()
            elif not rel_watched.startswith("."):
                raise IgnoreEvent()

            # Ensure the dot prefix to the path to make it obvious that this
            # is a relative path
            if not rel_path.startswith("."):
                rel_path = os.path.join(".", rel_path)

            return rel_path
        except ValueError as e:
            raise IgnoreEvent() from e

    def _drain_queue(self, timeout=0.5):
        event = self.events.get(block=True, timeout=timeout)
        latest_events = {event.src_path: event}
        try:
            # Allow a bit of time for the queue to fill
            if self.events.qsize() == 0:
                time.sleep(0.25)
            # Started filling? allow a little bit more time
            if self.events.qsize() > 0:
                time.sleep(0.4)

            # Start draining
            while self.events.qsize() > 0:
                event = self.events.get_nowait()
                # Only keep the latest event for a given file path
                latest_events[event.src_path] = event

        except queue.Empty:
            pass
        finally:
            return latest_events.values()

    def _filter_events(self, latest_events, stop_threashold=None):
        sync_events = []
        for event in latest_events:
            filtered = False
            for file_filter in self.filters:
                with self.terminal_lock():
                    if file_filter(event=event) is False:
                        filtered = True
                        break
            if not filtered:
                sync_events.append(event)
            if stop_threashold is not None and len(sync_events) > stop_threashold:
                return sync_events

        return sync_events

    def run(self):
        while self._running:
            try:
                latest_events = self._drain_queue()
                sync_events = self._filter_events(latest_events, stop_threashold=self.full_sync_threashold)
                if len(sync_events) >= self.full_sync_threashold:
                    with self.terminal_lock():
                        self.backend.sync_project(self.all_watched_dirs, **self.backend_options)
                else:
                    for event in sync_events:
                        with self.terminal_lock():
                            self._sync(event)
            except queue.Empty:
                time.sleep(0.001)

    def catch_all_handler(self, event):
        try:
            # Add sync event to the sync queue
            self.events.put(event)
        except queue.Full:
            # It's acceptable for events to be rejected from the queue
            # because a busy queue will trigger a full-sync
            pass

    def on_moved(self, event):
        self.catch_all_handler(event)

    def on_created(self, event):
        self.catch_all_handler(event)

    def on_deleted(self, event):
        self.catch_all_handler(event)

    def on_modified(self, event):
        self.catch_all_handler(event)


def split_destination(destination):
    kube = "kube://"
    if destination.lower().startswith(kube):
        return "kube-rsync", destination[len(kube) :]
    else:
        return "file-rsync", destination


def filter_missing_paths(paths: list):
    missing_paths = []
    existing_paths = []
    for p in paths:
        if os.path.exists(p):
            existing_paths.append(p)
        else:
            missing_paths.append(p)
    return missing_paths, existing_paths


def check_that_source_and_destination_are_unrelated(source_paths, destination):
    colon_split = destination.split(":")
    if len(colon_split) == 2:
        # Looks like destination is a remote server:path
        return

    abs_destination = os.path.abspath(destination)
    destination_parent, _ = os.path.split(abs_destination)

    for path in source_paths:
        abs_path = os.path.abspath(path)
        if destination_parent.startswith(abs_path):
            raise RelatedLocationsError(
                "The destination location must not descend from any of the sources.\n"
                "Please verify that the dfsync section from pyproject.yaml is valid."
            )
        elif abs_path.startswith(abs_destination):
            raise RelatedLocationsError(
                "Source locations must not descend from the destination.\n"
                "Please verify that the dfsync section from pyproject.yaml is valid."
            )


def has_destination_optics(destination):
    # Returns true if the given argument looks like a destination
    # e.g. a kubernetes slug or a ssh "user@host:path" slug
    is_kube = destination.lower().startswith("kube://")

    is_ssh = ":/" in destination or ":~" in destination
    if ":" in destination:
        user_host, _ = destination.split(":")[:2]
        is_ssh = "@" in user_host or is_ssh

    return is_kube or is_ssh


@click.group(cls=DefaultGroup, default="sync", default_if_no_args=False, context_settings=dict(max_content_width=999))
def main():
    pass


@main.command()
def version():
    installed_version = get_installed_version()
    click.echo(f"{installed_version}")

    latest_version = get_latest_version()
    if is_older_version(installed_version, latest_version):
        click.echo(f"Latest version is {latest_version}, please upgrade!")


@main.command()
@click.option("--kube-host", default=None, help="Kubernetes api host server address/hostname", type=str)
@click.option("--credentials", default=sys.stdin, help="compose file to work with", type=click.File("r"))
def import_kube_host(kube_host=None, credentials=None):
    """
    Import the credentials for a kubernetes cluster into the local ~/.kube/config
    This is designed to be easily used in conjunction with an ssh command, for e.g.

    ssh user@kube-host -C "sudo cat /root/.kube/config" | dfsync import-kube-host --kube-host=https://kube-host:6443
    """
    patch = contextualize_kube_credentials(kube_host, credentials)
    update_local_kube_config(patch)


@main.command()
@click.argument("source", nargs=-1)
@click.argument("destination", default="", nargs=1)
@click.option("--supervisor/--no-supervisor", default=False, help="Try to install supervisor in container", type=bool)
@click.option("--kube-host", default=None, help="Kubernetes api host server address/hostname", type=str)
@click.option("--pod-timeout", default=30, help="Pod reconfiguration timeout (default is 30 seconds)", type=int)
@click.option("--full-sync/--no-full-sync", default=True, help="On startup, sync all files to destination", type=bool)
def sync(source, destination, supervisor, kube_host, pod_timeout, full_sync):
    """
    Watches a folder for changes and propagates all file changes to a destination.

    SOURCE is a path to the folder that dfsync will monitor for changes (or current dir if missing)

    DESTINATION is a destination path / psuedo-url

    Example usages:

    \b
    1. Watch a dir and sync changes to a target on the local filesystem
       dfsync src /home/user/absolute/paths/to/target/dir
       dfsync . ../../relative/path/to/target/dir
       dfsync ../../relative/path/to/target/dir (if source_dir is omitted, will watch the current dir)

    \b
    2. Watch a dir and sync changes to a remote target using ssh
       dfsync src user@target-host:/home/user/absolute/paths/to/remote/host/dir
       dfsync build user@target-host:~/relative/path/to/user/home

    \b
    3. Watch a dir and sync changes to kubernetes pod/containers using the given image name
       dfsync src kube://image-name-of-awesome-api:/home/user/awesome-api
       dfsync kube://quay.io/project/name-of-container-image:/home/path/within/container/awesome-api

    \b
    dfsync is:
    * git-aware: changes to git internals, files matching .gitignore patterns and untracked files will be ignored
    * editor-aware: changes to temporary files created by source code editors will be ignored
    * transparent: every action is diligently logged in the console
    """
    logging.basicConfig(
        level=logging.WARN,
        format="%(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    paths = ["."] if len(source) == 0 else source
    config = read_config(destination, *paths)
    add_user_ignored_patterns_filter(config.ignore_files)

    destination_dir = destination
    if len(source) == 0 and config.destination and not has_destination_optics(destination):
        destination_dir = config.destination
        paths = [destination] if destination else paths
    missing, paths = filter_missing_paths([*config.additional_sources, *paths])
    if len(missing) > 0 and len(paths) > 0:
        click.echo(f"Source file/dirs not found: {', '.join(missing)}")

    backend, destination_dir = split_destination(destination_dir)
    try:
        if len(paths) == 0:
            raise ValueError("No source file/dirs found")
        elif len(missing) > 0:
            click.echo(f"Using source file/dirs {', '.join(paths)}")

        backend_options = dict(
            destination_dir=destination_dir,
            supervisor=supervisor,
            kube_host=kube_host,
            pod_timeout=pod_timeout,
            container_command=config.container_command,
            full_sync=full_sync,
        )

        backend_engine_factory = BACKENDS.get(backend)
        backend_engine = backend_engine_factory(**backend_options)
        if backend_engine is None:
            raise ValueError("Backend not found: {}".format(backend))

        check_that_source_and_destination_are_unrelated(paths, destination_dir)
        click.echo("Trying {} to '{}'".format(backend, destination_dir))

    except RelatedLocationsError as e:
        click.echo(
            "Trying {} from source: {} to destination: '{}'\n".format(
                backend,
                ", ".join([f"'{os.path.abspath(p)}'" for p in paths]),
                os.path.abspath(destination_dir),
            )
        )
        click.echo(str(e))
        return -1

    except ValueError as e:
        click.echo(
            "Trying {} from source: {} to destination: '{}'\n".format(
                backend,
                ", ".join([f"'{p}'" for p in paths or missing]),
                destination_dir,
            )
        )
        click.echo(str(e))
        return -1

    checker = AsyncVersionChecker()
    controller = KeyController()

    handlers = []
    observer = Observer()
    for p in paths:
        event_handler = FileChangedEventHandler(
            backend_engine, watched_dir=p, all_watched_dirs=paths, input_controller=controller, **backend_options
        )
        handlers.append(event_handler)
        event_handler.start()
        observer.schedule(event_handler, os.path.abspath(p), recursive=True)

    controller.on_key(
        "f",
        description="to trigger a full sync",
        action=partial(backend_engine.sync_project, paths, **backend_options),
    )
    controller.on_key(
        "x",
        description="to exit",
        action=partial(thread_manager.stop, "Exiting."),
    )

    try:
        backend_engine.on_monitor_start(src_file_paths=paths, **backend_options)
        click.echo("Watching source dir(s): '{}'; press [Ctrl-C] to exit\n".format("', '".join(paths)))
        observer.start()

        checker.start()
        controller.help()
        controller.start()

        no_errors = True
        while no_errors and controller.is_running:
            time.sleep(0.2)
            for event_handler in handlers:
                if event_handler.raised_exception:
                    no_errors = False
                    break
            with controller.getch_lock():
                if checker.should_emit_upgrade_warning:
                    checker.set_emitted_upgrade_warning()
                    click.echo(checker.get_upgrade_warning())
            controller.raise_exceptions()

    except KeyboardInterrupt:
        thread_manager.stop()
        click.echo("Received [Ctrl-C], exiting.")

    except:
        thread_manager.stop()
        raise

    finally:
        observer.stop()
        thread_manager.stop()
        backend_engine.on_monitor_exit(**backend_options)
        if observer.ident is not None:
            # only join the observer if it was previously started
            observer.join()


if __name__ == "__main__":
    sys.exit(main() or 0)
