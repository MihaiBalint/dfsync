import sys
import time
import logging
from watchdog.observers import Observer
from watchdog.events import (
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
    FileSystemEventHandler,
)

from dfsync.backends import rsync_backend

logging.basicConfig(level=logging.INFO)


class FileChangedEventHandler(FileSystemEventHandler):
    def __init__(self, backend: str = "log", **kwargs):
        self.backend = getattr(self, "_{}_backend".format(backend), None)
        if self.backend is None:
            raise ValueError("Backend not found: {}".format(backend))
        self.backend_args = kwargs

    def _log_backend(self, event):
        logging.info(event)

    def _rsync_backend(self, event):
        rsync_backend(src_file_path=event.src_path, event=event, **self.backend_args)

    def catch_all_handler(self, event):
        event_classes = [FileCreatedEvent, FileDeletedEvent, FileModifiedEvent]
        for event_class in event_classes:
            if isinstance(event, event_class):
                self.backend(event)
                return

    def on_moved(self, event):
        self.catch_all_handler(event)

    def on_created(self, event):
        self.catch_all_handler(event)

    def on_deleted(self, event):
        self.catch_all_handler(event)

    def on_modified(self, event):
        self.catch_all_handler(event)


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

    print("Destination dir: '{}'".format(destination_dir))
    print("Watching dir: '{}', press [Ctrl-C] to exit\n".format(path))
    event_handler = FileChangedEventHandler("rsync", destination_dir=destination_dir)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
