import click
import os
import os.path
import sys
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from dfsync.backends import rsync_backend
from dfsync.backends import kube_backend
from dfsync.filters import ALL_FILTERS

logging.basicConfig(level=logging.WARN)

BACKENDS = {
    # File sync backends
    "rsync": rsync_backend,
    "kube": kube_backend,
}


class IgnoreEvent(Exception):
    pass


class FileChangedEventHandler(FileSystemEventHandler):
    def __init__(self, backend: str = "log", watched_dir: str = ".", **kwargs):
        self.filters = [*ALL_FILTERS]

        self.backend = backend
        self.backend_options = kwargs
        self.raised_exception = False
        self.abs_watched_dir = os.path.abspath(watched_dir)

    def _log_backend(self, event):
        logging.info(event)

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

    def _propagate_event(self, event):
        for file_filter in self.filters:
            if file_filter(event=event) is False:
                return
        self._sync(event)

    def catch_all_handler(self, event):
        try:
            self._propagate_event(event)
        except IgnoreEvent:
            pass
        except:
            self.raised_exception = True
            raise

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
        return "kube", destination[len(kube) :]
    else:
        return "rsync", destination


@click.command()
@click.argument("source", nargs=-1)
@click.argument("destination", default="", nargs=1)
@click.option("--supervisor/--no-supervisor", default=False, help="Try to install supervisor in container", type=bool)
@click.option("--kube-host", default=None, help="Kubernetes api host server address/hostname", type=str)
@click.option("--pod-timeout", default=30, help="Pod reconfiguration timeout (default is 30 seconds)", type=int)
def main(source, destination, supervisor, kube_host, pod_timeout):
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
    destination_dir = destination

    backend, destination_dir = split_destination(destination_dir)
    click.echo("Destination, {}: '{}'".format(backend, destination_dir))

    backend_options = dict(
        destination_dir=destination_dir, supervisor=supervisor, kube_host=kube_host, pod_timeout=pod_timeout
    )
    backend_engine_factory = BACKENDS.get(backend)
    backend_engine = backend_engine_factory(**backend_options)
    if backend_engine is None:
        raise ValueError("Backend not found: {}".format(backend))

    handlers = []
    observer = Observer()
    for p in paths:
        event_handler = FileChangedEventHandler(backend_engine, watched_dir=p, **backend_options)
        handlers.append(event_handler)
        observer.schedule(event_handler, os.path.abspath(p), recursive=True)
    try:
        backend_engine.on_monitor_start(src_file_paths=paths, **backend_options)
        click.echo("Watching dir(s): '{}'; press [Ctrl-C] to exit\n".format("', '".join(paths)))
        observer.start()

        no_errors = True
        while no_errors:
            for event_handler in handlers:
                if event_handler.raised_exception:
                    no_errors = False
                    break
            time.sleep(0.2)
    except KeyboardInterrupt:
        click.echo("Received [Ctrl-C], exiting.")
    finally:
        observer.stop()
        backend_engine.on_monitor_exit(**backend_options)
        observer.join()


if __name__ == "__main__":
    main()
