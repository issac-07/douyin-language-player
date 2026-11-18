"""Single inference worker with reorderable waiting tasks; running work is never interrupted."""
import threading
from concurrent.futures import Future


class TranslationQueue:
    def __init__(self):
        self.condition = threading.Condition()
        self.waiting = []
        self.priorities = {}
        self.sequence = 0
        self.closed = False
        self.thread = threading.Thread(target=self._run, name='translation', daemon=True)
        self.thread.start()

    def prioritize(self, keys):
        with self.condition:
            self.priorities = {key: rank for rank, key in reversed(list(enumerate(keys)))}
            self.condition.notify()

    def is_priority(self, key):
        with self.condition:
            return self.priorities.get(key, 1000000) < 10

    def submit(self, fn, *args):
        future = Future()
        with self.condition:
            if self.closed:
                raise RuntimeError('Translation queue is closed')
            self.sequence += 1
            self.waiting.append((self.sequence, future, fn, args))
            self.condition.notify()
        return future

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.waiting or self.closed)
                if not self.waiting:
                    return
                task = min(self.waiting, key=lambda item: (self.priorities.get(item[3][0], 1000000) if item[3] else -1, item[0]))
                self.waiting.remove(task)
            _, future, fn, args = task
            if future.set_running_or_notify_cancel():
                try:
                    future.set_result(fn(*args))
                except BaseException as exc:
                    future.set_exception(exc)

    def shutdown(self, wait=True, cancel_futures=False):
        with self.condition:
            self.closed = True
            if cancel_futures:
                for _, future, _, _ in self.waiting:
                    future.cancel()
                self.waiting.clear()
            self.condition.notify_all()
        if wait:
            self.thread.join()
