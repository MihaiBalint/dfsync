import logging
import subprocess


def rsync_backend(src_file_path, destination_dir: str = None, **kwargs):
    logging.error(
        "Rsync backend not implemented (changed: {}, copy to: {})".format(
            src_file_path, destination_dir
        )
    )
