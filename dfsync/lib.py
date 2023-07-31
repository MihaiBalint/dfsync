import time, threading


class ControlledThreadedOperation:
    def __init__(self):
        self._running = False
        self._thread = threading.Thread(target=self.run)

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self, message: str = None):
        self._running = False

    @property
    def is_running(self):
        return self._running

    @property
    def is_completed(self):
        return self._running == False

    def run(self):
        while self._running:
            try:
                self._run_once()
            except:
                time.sleep(0.001)

    def _run_once(self):
        time.sleep(0.001)
