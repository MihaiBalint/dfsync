import logging, os, os.path, select, subprocess, time

from dfsync.filters import list_files_to_ignore
from dfsync.lib import ControlledThreadedOperation

EVENT_TYPE_MAP = {
    "created": "Created",
    "deleted": "Deleted",
    "default": "Synced",
    "full-sync": "Full Sync",
}


class StopStreamReader(Exception):
    pass


class RsyncStreamReader(ControlledThreadedOperation):
    def __init__(self, stream):
        super().__init__()
        if stream is None:
            raise ValueError("Rsync status stream must not be None")

        self.stream = stream
        self.timeout = 300.0

        self.rsync_stats = None
        self.rsync_error = None
        self.rsync_permission_error_count = 0
        self.stream_closed = False

    def read_lines(self):
        spoll = select.poll()
        spoll.register(self.stream, select.POLLIN)
        try:
            line_timestamp = time.monotonic()
            elapsed = 0

            while elapsed < self.timeout:
                if spoll.poll(0):
                    line = self.stream.readline()
                    if len(line) > 0:
                        line_timestamp = time.monotonic()
                        yield line.decode("utf8")
                    else:
                        return
                else:
                    time.sleep(0.1)
                elapsed = time.monotonic() - line_timestamp

            if elapsed >= self.timeout:
                raise subprocess.TimeoutExpired(cmd="read_lines", timeout=self.timeout)
        except ValueError:
            pass

        finally:
            self.stream_closed = True

            try:
                spoll.unregister(self.stream)
            except:
                # don't care at this point
                pass

            try:
                self.stream.close()
            except:
                # don't care at this point
                pass

    def run(self):
        try:
            for line in self.read_lines():
                if line and line.startswith("sent "):
                    # stdout
                    self.rsync_stats = line.strip()
                elif line and line.startswith("X11 forwarding"):
                    # stdout
                    pass
                elif line and line.startswith("building file list"):
                    # stdout
                    pass
                elif line and line.startswith("total size"):
                    # stdout
                    pass
                elif line and line.startswith("rsync error"):
                    # stderr
                    self.rsync_error = line.strip()
                elif line and line.startswith("rsync: ") and "failed: Permission" in line:
                    # stderr
                    self.rsync_permission_error_count += 1
                elif line and line.startswith("rsync: ") and "failed: Resource busy" in line:
                    # stderr
                    self.rsync_permission_error_count += 1

                elif line and line.strip():
                    # echo(line.strip())
                    pass

                if not self.is_running:
                    self.timeout = 1.0

        except (subprocess.TimeoutExpired, StopStreamReader):
            # Stop silently
            pass

    def stop(self, *args, **kwargs):
        super().stop(*args, **kwargs)
        self.stream.close()

        while not self.stream_closed:
            time.sleep(1.0)


def echo(msg=""):
    print(f"{msg}")


class FileRsync:
    def __init__(self, full_sync=None, **kwargs):
        valued_args = {k: kwargs.get(k) for k in ["kube_host", "container_command"] if kwargs.get(k) is not None}

        if len(valued_args) != 0:
            keys = ", ".join(valued_args.keys())
            message = f"Plain file-rsync operation does not support given arguments: {keys}."
            kube_hints = ["kube_host", "pod_timeout", "container_command"]
            if any(h in keys for h in kube_hints):
                message = (
                    f"{message}\n"
                    "Are you trying to use dfsync with kubernetes? Your config might be incomplete/missing!\n"
                    "Please verify that the dfsync section from pyproject.yaml is valid.\n"
                )
            raise ValueError(message)

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
        event_type_str = EVENT_TYPE_MAP.get(event_type) or EVENT_TYPE_MAP.get("default")
        if event_type == "full-sync":
            echo(f"{event_type_str} running")

        rsh = ["--rsh={}".format(rsh)] if rsh is not None else []
        blocking_io = ["--blocking-io"] if blocking_io else []

        src_file_paths = [sanitize_relative_path(src_path) for src_path in src_file_paths]
        destination_dir = destination_dir.rstrip("/")
        destination_dir = "{}/".format(destination_dir)

        if event_type == "deleted":
            if len(src_file_paths) > 1:
                echo("multi-source delete is not supported")
            rsync_cmd = self._get_rsync_cmd_on_file_delete(src_file_paths[0], destination_dir, blocking_io, rsh)
        elif event_type == "full-sync":
            src_paths = [p or "./" for p in src_file_paths]
            rsync_cmd = self._get_rsync_cmd_on_full_sync(src_paths, destination_dir, blocking_io, rsh)
        else:
            rsync_cmd = [
                "rsync",
                "-Rvx",
                "--temp-dir=/tmp",
                "--delay-updates",
                *blocking_io,
                *rsh,
                *src_file_paths,
                destination_dir,
            ]

        logging.debug("rsync command: {}".format(" ".join(rsync_cmd)))

        popen_args = {}
        if rsync_cwd:
            popen_args.update(dict(cwd=rsync_cwd))
        try:
            rsync_process = subprocess.Popen(
                rsync_cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=rsh_env,
                **popen_args,
            )
            stdout = RsyncStreamReader(rsync_process.stdout)
            stdout.start()

            stderr = RsyncStreamReader(rsync_process.stderr)
            stderr.start()

            return_code = rsync_process.wait(timeout=None)

            stdout.stop()
            stderr.stop()

            if stdout.rsync_stats:
                echo(f"  {stdout.rsync_stats}")

            if return_code != 0:
                if stderr.rsync_error:
                    echo(f"  {stderr.rsync_error}")
                else:
                    echo(f"  rsync exit code: {return_code}")

                if stderr.rsync_permission_error_count > 0:
                    files = "file" if stderr.rsync_permission_error_count == 1 else "files"
                    echo(
                        f"  {stderr.rsync_permission_error_count} {files} had permission or other issues on destination"
                    )

                if return_code != 23:
                    raise subprocess.CalledProcessError(returncode=return_code, cmd=rsync_cmd)

        except:
            echo("Sync failed")
            env_str = "N/A"
            if rsh_env:
                env_str = " ".join(f"{k}={v}" for k, v in rsh_env.items() if k not in os.environ.keys())
            echo(f"Env Var: {env_str}")
            cmd_str = " ".join(f"'{arg}'" if " " in arg else arg for arg in rsync_cmd)
            echo(f"Command: {cmd_str}")
            raise

        if len(src_file_paths) == 1:
            echo("{} {}".format(event_type_str, src_file_paths[0]))
        else:
            echo("{} {}".format(event_type_str, src_file_paths))

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
            "--temp-dir=/tmp",
            "--delay-updates",
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
