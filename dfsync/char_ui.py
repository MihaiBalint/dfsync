import time, threading
from functools import partial
from collections import namedtuple


class _GetchUnix:
    def __call__(self):
        import sys, tty, termios

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


getch = None
try:
    import msvcrt

    # MS Windows
    getch = msvcrt.getch()

except ImportError:
    getch = _GetchUnix()


class KeyHandlerException(Exception):
    pass


KeyHandler = namedtuple("KeyHandler", "keys description action")


class KeyController:
    def __init__(self):
        self.handlers = []
        self.key_handlers = {}
        self._running = False
        self._thread = threading.Thread(target=self.run)
        self._exception = None

        self.on_key("h", "?", description="for help", action=self.help)
        self.on_key("\r", description=None, action=self.echo)
        self.on_key("\x03", description=None, action=self._keyboard_interrupt)

    @property
    def is_running(self):
        return self._running

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self, message: str = None):
        if message:
            self.echo(message)
        self._running = False

    def run(self):
        while self._running:
            k = getch()
            handler = self.key_handlers.get(k)
            try:
                if handler is not None:
                    handler.action()
            except (Exception, KeyboardInterrupt) as e:
                self._exception = e

    def on_key(self, *keys, description: str = None, action=None):
        if action is None:
            raise ValueError("'action' cannot be None")
        handler = KeyHandler(keys=keys, description=description, action=action)
        self.handlers.append(handler)
        for k in keys:
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
