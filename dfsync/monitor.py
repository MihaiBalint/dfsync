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

        self.backend = BACKENDS.get(backend)
        if self.backend is None:
            raise ValueError("Backend not found: {}".format(backend))
        self.backend_args = kwargs
        self.raised_exception = False
        self.abs_watched_dir = os.path.abspath(watched_dir)

    def _log_backend(self, event):
        logging.info(event)

    def _sync(self, event):
        # It seems like in some contexts, event.src_path will be an absolute path
        # and in some other contexts, it will be a relative path

        self.backend.sync(
            src_file_path=self._get_path_relative_to_watched_dir(event.src_path),
            event=event,
            watched_dir=self.abs_watched_dir,
            **self.backend_args
        )

    def _get_path_relative_to_watched_dir(self, path):
        try:
            abs_path = os.path.abspath(path)
            common = os.path.commonpath([self.abs_watched_dir, abs_path])

            rel_watched = os.path.relpath(self.abs_watched_dir, start=common)
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

    def on_monitor_start(self):
        self.backend.on_monitor_start(**self.backend_args)

    def on_monitor_exit(self):
        self.backend.on_monitor_exit(**self.backend_args)


def split_destination(destination):
    kube = "kube://"
    if destination.lower().startswith(kube):
        return "kube", destination[len(kube) :]
    else:
        return "rsync", destination


def main():
    logging.basicConfig(
        level=logging.WARN,
        format="%(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    path = "."
    destination_dir = None

    if len(sys.argv) > 2:
        path = sys.argv[1]
        destination_dir = sys.argv[2]
    elif len(sys.argv) > 1:
        destination_dir = sys.argv[1]
    else:
        print("Usage: {} [source_dir] <destination_path>\n".format(sys.argv[0]))
        sys.exit(1)

    backend, destination_dir = split_destination(destination_dir)
    print("Destination, {}: '{}'".format(backend, destination_dir))
    event_handler = FileChangedEventHandler(
        backend, destination_dir=destination_dir, watched_dir=path
    )
    observer = Observer()
    observer.schedule(event_handler, os.path.abspath(path), recursive=True)
    try:
        event_handler.on_monitor_start()
        print("Watching dir: '{}', press [Ctrl-C] to exit\n".format(path))
        observer.start()
        while event_handler.raised_exception is False:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Received [Ctrl-C], exiting.")
    finally:
        observer.stop()
        event_handler.on_monitor_exit()
        observer.join()


if __name__ == "__main__":
    main()
