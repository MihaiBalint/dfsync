import logging
import os.path
import subprocess

from dfsync.filters import list_files_to_ignore

EVENT_TYPE_MAP = {
    "created": "Created",
    "deleted": "Deleted",
    "default": "Synced",
    "full-sync": "Full Sync",
}


class FileRsync:
    def __init__(self):
        pass

    def sync(self, src_file_path, event=None, **kwargs):
        event_type = "default"
        if not os.path.exists(src_file_path):
            event_type = "deleted"
        elif event is not None:
            event_type = event.event_type
        return self._sync(src_file_path, event_type=event_type, **kwargs)

    def _sync(
        self,
        src_file_path,
        destination_dir: str = None,
        event_type="default",
        rsh=None,
        rsh_env=None,
        blocking_io=False,
        **kwargs,
    ):
        rsh = ["--rsh={}".format(rsh)] if rsh is not None else []
        blocking_io = ["--blocking-io"] if blocking_io else []

        src_file_path = sanitize_relative_path(src_file_path)
        destination_dir = destination_dir.rstrip("/")
        destination_dir = "{}/".format(destination_dir)

        if event_type == "deleted":
            rsync_cmd = self._get_rsync_cmd_on_file_delete(
                src_file_path, destination_dir, blocking_io, rsh
            )
        elif event_type == "full-sync":
            rsync_cmd = self._get_rsync_cmd_on_full_sync(
                src_file_path or "./", destination_dir, blocking_io, rsh
            )
        else:
            rsync_cmd = [
                "rsync",
                "-Rvx",
                *blocking_io,
                *rsh,
                src_file_path,
                destination_dir,
            ]

        logging.debug("rsync command: {}".format(" ".join(rsync_cmd)))

        subprocess.check_call(
            rsync_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=rsh_env,
        )

        event_type = EVENT_TYPE_MAP.get(event_type) or EVENT_TYPE_MAP.get("default")
        print("{} {}".format(event_type, src_file_path))

    def _get_rsync_cmd_on_file_delete(
        self, src_file_path, destination_dir: str, blocking_io: list, rsh: list
    ):
        src_dir, file_name = os.path.split(src_file_path)
        intermediate_paths = [file_name]
        while len(src_dir) > 0 and src_dir.strip() != ".":
            if os.path.isdir(src_dir):
                break
            src_dir, deleted_dir = os.path.split(src_dir)
            intermediate_paths = [
                os.path.join(deleted_dir, p) for p in ["", *intermediate_paths]
            ]

        filters = ["--filter=+,r {}".format(p) for p in intermediate_paths]

        if not src_dir:
            src_dir = src_dir or "./"
        else:
            destination_dir = "{}{}/".format(destination_dir, src_dir)
            src_dir = "{}/".format(src_dir)

        cmd = [
            "rsync",
            "-rvx",
            "--delete",
            "--filter=-,s *",
            *filters,
            "--filter=-,r *",
            *blocking_io,
            *rsh,
            src_dir,
            destination_dir,
        ]
        return cmd

    def _get_rsync_cmd_on_full_sync(
        self, src_file_path, destination_dir: str, blocking_io: list, rsh: list
    ):
        filters = ["--filter=- {}".format(f) for f in list_files_to_ignore()]
        return [
            "rsync",
            "-rvx",
            "--delete",
            "--filter=- .git/",
            *filters,
            *blocking_io,
            *rsh,
            src_file_path,
            destination_dir,
        ]

    def sync_project(self, src_file_path, **kwargs):
        return self._sync(src_file_path, event_type="full-sync", **kwargs)

    def on_monitor_start(self, destination_dir: str = None, **kwargs):
        pass

    def on_monitor_exit(self, destination_dir: str = None, **kwargs):
        pass


def sanitize_relative_path(path):
    while True:
        if path.startswith("./"):
            path = path[2:]
            continue
        if path.startswith("/"):
            path = path[1:]
            continue
        break
    return path


rsync_backend = FileRsync()
