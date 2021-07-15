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
    def __init__(self, **kwargs):
        pass

    def sync(self, src_file_path, event=None, watched_dir: str = None, **kwargs):
        rsync_cwd = watched_dir
        event_type = "default"
        src_abs_path = os.path.join(watched_dir, src_file_path) if watched_dir else src_file_path
        if not os.path.exists(src_abs_path):
            event_type = "deleted"
        elif event is not None:
            event_type = event.event_type

        return self._sync([src_file_path], event_type=event_type, rsync_cwd=rsync_cwd, **kwargs)

    def _sync(
        self,
        src_file_paths,
        destination_dir: str = None,
        event_type="default",
        rsh=None,
        rsh_env=None,
        blocking_io=False,
        rsync_cwd=None,
        **kwargs,
    ):
        rsh = ["--rsh={}".format(rsh)] if rsh is not None else []
        blocking_io = ["--blocking-io"] if blocking_io else []

        src_file_paths = [sanitize_relative_path(src_path) for src_path in src_file_paths]
        destination_dir = destination_dir.rstrip("/")
        destination_dir = "{}/".format(destination_dir)

        if event_type == "deleted":
            if len(src_file_paths) > 1:
                print("multi-source delete is not supported")
            rsync_cmd = self._get_rsync_cmd_on_file_delete(src_file_paths[0], destination_dir, blocking_io, rsh)
        elif event_type == "full-sync":
            src_paths = [p or "./" for p in src_file_paths]
            rsync_cmd = self._get_rsync_cmd_on_full_sync(src_paths, destination_dir, blocking_io, rsh)
        else:
            rsync_cmd = [
                "rsync",
                "-Rvx",
                *blocking_io,
                *rsh,
                *src_file_paths,
                destination_dir,
            ]

        logging.debug("rsync command: {}".format(" ".join(rsync_cmd)))

        popen_args = {}
        if rsync_cwd:
            popen_args.update(dict(cwd=rsync_cwd))
        subprocess.check_call(
            rsync_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=rsh_env,
            **popen_args,
        )

        event_type = EVENT_TYPE_MAP.get(event_type) or EVENT_TYPE_MAP.get("default")
        if len(src_file_paths) == 1:
            print("{} {}".format(event_type, src_file_paths[0]))
        else:
            print("{} {}".format(event_type, src_file_paths))

    def _get_rsync_cmd_on_file_delete(self, src_file_path, destination_dir: str, blocking_io: list, rsh: list):
        src_dir, file_name = os.path.split(src_file_path)
        intermediate_paths = [file_name]
        while len(src_dir) > 0 and src_dir.strip() != ".":
            if os.path.isdir(src_dir):
                break
            src_dir, deleted_dir = os.path.split(src_dir)
            intermediate_paths = [os.path.join(deleted_dir, p) for p in ["", *intermediate_paths]]

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

    def _get_rsync_cmd_on_full_sync(self, src_file_paths: list, destination_dir: str, blocking_io: list, rsh: list):
        filters = ["--filter=- {}".format(f) for f in list_files_to_ignore()]
        return [
            "rsync",
            "-rvx",
            "--delete",
            "--filter=- .git/",
            *filters,
            *blocking_io,
            *rsh,
            *[f"{p}/" for p in src_file_paths],
            destination_dir,
        ]

    def sync_project(self, src_file_paths, **kwargs):
        return self._sync(src_file_paths, event_type="full-sync", **kwargs)

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


rsync_backend = FileRsync
