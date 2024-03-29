import time, threading
from functools import partial
from collections import namedtuple
from contextlib import contextmanager
from dfsync.lib import ControlledThreadedOperation

# TODO: consider using prompt-toolkit package
# https://python-prompt-toolkit.readthedocs.io/en/master/pages/asking_for_input.html#prompt-in-an-asyncio-application


class _GetchUnix:
    def __init__(self):
        self.capture = True
        self.raw_lock = threading.Lock()

    def __call__(self):
        import sys, tty, termios, selectors

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        sel = selectors.DefaultSelector()
        sel.register(sys.stdin, selectors.EVENT_READ)
        ch = None
        while ch is None and self.capture:
            with self.raw_lock:
                if not self.capture:
                    break
                try:
                    tty.setraw(sys.stdin.fileno())
                    events = sel.select(timeout=0.1)
                    if events:
                        key, _ = events[0]
                        ch = key.fileobj.read(1)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            time.sleep(0.001)
        return ch

    def stop(self):
        self.capture = False
        with self.raw_lock:
            # This is here to make sure that the tty state is normal (not raw)
            self.capture = False


getch = None

try:
    import msvcrt

    # MS Windows
    getch = msvcrt.getch()
    raise RuntimeError("Windows isn't supported")

except ImportError:
    getch = _GetchUnix()


class KeyHandlerException(Exception):
    pass


class KeyHandler:
    def __init__(self, keys, description, action, strict_case):
        self.keys = keys
        self.description = description
        self.action = action

        self.event_keys = set(keys)
        if not strict_case:
            self.event_keys.update([k.lower() for k in self.keys])
            self.event_keys.update([k.upper() for k in self.keys])


class KeyController(ControlledThreadedOperation):
    def __init__(self):
        super().__init__()
        self.handlers = []
        self.key_handlers = {}
        self._exception = None

        self.on_key("h", "?", description="for help", action=self.help)
        self.on_key("\r", description=None, action=self.echo)
        self.on_key("\x03", description=None, action=self._keyboard_interrupt)

    def stop(self, message: str = None):
        getch.stop()
        if message:
            self.echo(message)
        super().stop()

    @contextmanager
    def getch_lock(self):
        with getch.raw_lock:
            yield self

    def run(self):
        while self._running:
            k = getch()
            if k is None:
                continue
            handler = self.key_handlers.get(k)
            try:
                if handler is not None:
                    handler.action()
            except (Exception, KeyboardInterrupt) as e:
                self._exception = e

    def on_key(self, *keys, description: str = None, action=None, strict_case=False):
        if action is None:
            raise ValueError("'action' cannot be None")
        handler = KeyHandler(keys=keys, description=description, action=action, strict_case=strict_case)
        self.handlers.append(handler)
        for k in handler.event_keys:
            self.key_handlers[k] = handler

    def raise_exceptions(self):
        if self._exception is not None and isinstance(self._exception, KeyboardInterrupt):
            raise KeyboardInterrupt() from self._exception

        elif self._exception is not None:
            raise KeyHandlerException() from self._exception

    def _keyboard_interrupt(self):
        self.stop()
        raise KeyboardInterrupt()

    def echo(self, msg=""):
        print(msg)

    def help(self):
        self.echo()
        for handler in self.handlers:
            if handler.description is None:
                # Hidden handlers
                continue
            keys = ",".join(handler.keys)
            self.echo(f"Press [{keys}] {handler.description}")
