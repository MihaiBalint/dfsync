from enum import Enum
import platform
import subprocess
import time
import threading


class ThreadedOperationsManager:
    def __init__(self):
        self.threads = []

    def stop(self, *args, **kwargs):
        for thread in self.threads:
            thread.stop(*args, **kwargs)

    def register_threaded_operation(self, op):
        self.threads.append(op)


thread_manager = ThreadedOperationsManager()


class ControlledThreadedOperation:
    def __init__(self):
        self._running = False
        self._thread = threading.Thread(target=self.run)
        thread_manager.register_threaded_operation(self)

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self, *args, **kwargs):
        self._running = False

    @property
    def is_running(self):
        return self._running

    @property
    def is_completed(self):
        return self._running is False

    def run(self):
        while self._running:
            try:
                self._run_once()
            except Exception:
                time.sleep(0.001)

    def _run_once(self):
        time.sleep(0.001)


class RsyncFlavour(Enum):
    SAMBA_RSYNC = "SAMBA_RSYNC"
    OPEN_RSYNC = "OPENRSYNC"

    @property
    def executable(self):
        if platform.system() == "Darwin":  # Check if running on macOS
            if self == RsyncFlavour.SAMBA_RSYNC:
                return "/opt/homebrew/bin/rsync"
            elif self == RsyncFlavour.OPEN_RSYNC:
                return "/usr/bin/rsync"

        # Default fallback for other platforms or if paths don't exist
        return "rsync"

    @property
    def exists_installed(self):
        try:
            # Check if the executable exists and is executable
            result = subprocess.run(
                ["which", self.executable], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
            )
            if result.returncode != 0:
                return False

            # Additionally verify it can be executed
            result = subprocess.run(
                [self.executable, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
            )
            return result.returncode == 0
        except Exception:
            return False


def check_rsync() -> RsyncFlavour:
    try:
        result = subprocess.run(["rsync", "--version"], capture_output=True, text=True)
        version_text = result.stdout

        if "rsync.samba.org/" in version_text:
            return RsyncFlavour.SAMBA_RSYNC
        else:
            # Default to OpenRsync if we can't positively identify Samba rsync
            return RsyncFlavour.OPEN_RSYNC
    except (subprocess.SubprocessError, FileNotFoundError):
        # If rsync isn't available or fails, default to Samba rsync
        return RsyncFlavour.SAMBA_RSYNC
