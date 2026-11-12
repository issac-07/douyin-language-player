"""Bounded ordered pipelines. Each OCR lane owns its mutable engine/sessions."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter


def prefetch(samples, cancelled, capacity=2, on_decode=None):
    # Only the producer thread advances/closes the decoder generator.
    def take():
        if cancelled():
            return None
        started = perf_counter()
        try:
            return next(samples, None)
        finally:
            if on_decode is not None:
                on_decode(perf_counter() - started)
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='frame-prefetch')
    pending = deque()
    try:
        for _ in range(capacity):
            pending.append(pool.submit(take))
        while pending and not cancelled():
            sample = pending.popleft().result()
            if sample is None:
                break
            pending.append(pool.submit(take))
            yield sample
    finally:
        for future in pending:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)
        samples.close()


class OCRLanes:
    def __init__(self, engines):
        self.engines = engines

    def observations(self, samples, cancelled):
        # One executor per mutable engine, never concurrent calls to one engine.
        pools = [ThreadPoolExecutor(max_workers=1, thread_name_prefix=f'ocr-lane-{i}') for i in range(len(self.engines))]
        pending = deque()
        iterator = iter(samples)
        def submit(index):
            sample = next(iterator, None)
            if sample is not None:
                pending.append((index, sample, pools[index].submit(self.engines[index].recognize, sample)))
        try:
            for index in range(len(pools)):
                if cancelled(): break
                submit(index)
            while pending and not cancelled():
                index, sample, future = pending.popleft()
                observation = future.result()
                if cancelled(): break
                yield sample, observation
                submit(index)
        finally:
            for _, _, future in pending:
                future.cancel()
            for pool in pools:
                pool.shutdown(wait=True, cancel_futures=True)
            if hasattr(samples, 'close'):
                samples.close()
