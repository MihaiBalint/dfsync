import logging
import os.path
import subprocess

EVENT_TYPE_MAP = {"created": "Created", "deleted": "Deleted", "default": "Synced"}


class FileRsync:
    def __init__(self):
        pass

    def sync(
        self,
        src_file_path,
        destination_dir: str = None,
        event=None,
        rsh=None,
        rsh_env=None,
        blocking_io=False,
        **kwargs
    ):
        src_dir, file_name = os.path.split(src_file_path)
        src_dir = src_dir.lstrip("./").rstrip("/")

        if len(src_dir.strip()) == 0:
            src_dir = "."
            destination_dir = destination_dir.rstrip("/")
        else:
            destination_dir = os.path.join(destination_dir.rstrip("/"), src_dir)

        src_dir = "{}/".format(src_dir)
        destination_dir = "{}/".format(destination_dir)

        # rsh = ["--rsh", rsh] if rsh is not None else []
        rsh = ["--rsh={}".format(rsh)] if rsh is not None else []
        blocking_io = ["--blocking-io"] if blocking_io else []

        rsync_cmd = [
            "rsync",
            "-rvx",
            "--delete",
            "--include=/{}".format(file_name),
            "--exclude=*",
            *blocking_io,
            *rsh,
            src_dir,
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

        event_type = EVENT_TYPE_MAP.get(event.event_type) or EVENT_TYPE_MAP.get(
            "default"
        )
        print("{} {}".format(event_type, src_file_path))

    def on_monitor_start(self, destination_dir: str = None, **kwargs):
        pass

    def on_monitor_exit(self, destination_dir: str = None, **kwargs):
        pass


rsync_backend = FileRsync()
