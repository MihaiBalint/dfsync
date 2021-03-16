import sys
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from dfsync.backends import rsync_backend
from dfsync.backends import kube_backend
from dfsync.filters import ALL_FILTERS

logging.basicConfig(level=logging.INFO)

BACKENDS = {
    # File sync backends
    "rsync": rsync_backend,
    "kube": kube_backend,
}


class FileChangedEventHandler(FileSystemEventHandler):
    def __init__(self, backend: str = "log", **kwargs):
        self.filters = [*ALL_FILTERS]

        self.backend = BACKENDS.get(backend)
        if self.backend is None:
            raise ValueError("Backend not found: {}".format(backend))
        self.backend_args = kwargs
        self.raised_exception = False

    def _log_backend(self, event):
        logging.info(event)

    def _sync(self, event):
        self.backend.sync(
            src_file_path=event.src_path, event=event, **self.backend_args
        )

    def _propagate_event(self, event):
        for file_filter in self.filters:
            if file_filter(event=event) is False:
                return
        self._sync(event)

    def catch_all_handler(self, event):
        try:
            self._propagate_event(event)
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


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
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
    print("Watching dir: '{}', press [Ctrl-C] to exit\n".format(path))
    event_handler = FileChangedEventHandler(backend, destination_dir=destination_dir)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()

    try:
        event_handler.on_monitor_start()
        while event_handler.raised_exception is False:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Received [Ctrl-C], exiting.")
    finally:
        observer.stop()
        event_handler.on_monitor_exit()
        observer.join()
