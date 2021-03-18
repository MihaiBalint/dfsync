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
        rsh = ["--rsh={}".format(rsh)] if rsh is not None else []
        blocking_io = ["--blocking-io"] if blocking_io else []

        src_file_path = src_file_path.lstrip("./")
        destination_dir = destination_dir.rstrip("/")
        destination_dir = "{}/".format(destination_dir)
        if event.event_type == "deleted":
            rsync_cmd = [
                "rsync",
                "-rRvx",
                "--delete",
                "--delete-excluded",
                # Guaranteed to not exist :)
                "--include=/f218a6b8a0607473ba376b07eff77eb9d4a7ee80/",
                "--exclude=/{}".format(src_file_path),
                *blocking_io,
                *rsh,
                "./",
                destination_dir,
            ]
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

        event_type = EVENT_TYPE_MAP.get(event.event_type) or EVENT_TYPE_MAP.get(
            "default"
        )
        print("{} {}".format(event_type, src_file_path))

    def _get_rsync_cmd_on_file_delete():
        """
rsync --dry-run -rRvx --delete --filter='-,s *' --filter='+r jack/'  --filter='+r jack/daniels' --filter='+,r jack/daniels/mihai' --filter='-,r *' ./ /Users/mihai/04-syneto/syneto-minerva-x/
        """

        pass

    def _get_rsync_cmd_on_file_delete(
        self, src_file_path, destination_dir: str, blocking_io: list, rsh: list,
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
        return [
            "rsync",
            "-rRvx",
            "--delete",
            "--delete-excluded",
            # Guaranteed to not exist :)
            "--include=/f218a6b8a0607473ba376b07eff77eb9d4a7ee80",
            "--exclude=/{}",
            *blocking_io,
            *rsh,
            src_dir,
            destination_dir,
        ]

    def on_monitor_start(self, destination_dir: str = None, **kwargs):
        pass

    def on_monitor_exit(self, destination_dir: str = None, **kwargs):
        pass


rsync_backend = FileRsync()
