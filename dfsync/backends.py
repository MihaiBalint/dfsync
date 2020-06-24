import logging
import os.path
import subprocess


def rsync_backend(src_file_path, destination_dir: str = None, **kwargs):
    src_dir = os.path.dirname(src_file_path)
    src_dir = src_dir.lstrip("./").rstrip("/")
    destination_dir = os.path.join(destination_dir, "{}/".format(src_dir))

    rsync_cmd = ["rsync", "-vx", src_file_path, destination_dir]
    logging.debug("rsync command: {}".format(" ".join(rsync_cmd)))
    subprocess.check_call(
        rsync_cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(src_file_path)
