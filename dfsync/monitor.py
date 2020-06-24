import sys
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileModifiedEvent, FileSystemEventHandler

logging.basicConfig(level=logging.DEBUG)


class FileChangedEventHandler(FileSystemEventHandler):
    def __init__(self, backend: str = "log"):
        self.backend = getattr(self, "_{}_backend".format(backend), None)
        if self.backend is None:
            raise ValueError("Backend not found: {}".format(backend))

    def _log_backend(self, event):
        logging.info(event)

    def _rsync_backend(self, event):
        logging.error(
            "Rsync backend not implemented (changed: {})".format(event.src_path)
        )

    def on_file_modified(self, event):
        self.backend(event)

    def catch_all_handler(self, event):
        if isinstance(event, FileModifiedEvent):
            self.on_file_modified(event)

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
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    event_handler = FileChangedEventHandler("rsync")
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
