"""Resolve requested OCR policy independently of device installation/probing."""
from dataclasses import dataclass

from app.services.ocr_engine import engine_identity


@dataclass(frozen=True)
class RuntimePlan:
    requested: str
    backend: str
    threads: int
    decoder: str
    reuse: str

    @property
    def identity(self):
        value = engine_identity()
        if self.backend != 'ort':
            import importlib.metadata
            try:
                version = importlib.metadata.version('openvino')
            except importlib.metadata.PackageNotFoundError:
                version = 'unavailable'
            value += f':{self.backend}:openvino-{version}:f32-v1'
        if self.threads != 2:
            value += f':threads={self.threads}'
        if self.decoder != 'seek':
            value += ':sequential-pts-v1'
        if self.reuse != 'accurate':
            value += ':white-strokes-exact-v1:max-reuse=2'
        return value


def resolve_runtime(settings):
    performance = settings.performance
    if performance is None:
        return RuntimePlan('cpu', 'ort', 2, 'seek', 'accurate')
    # Application Auto deliberately uses the measured, portable ORT CPU path.
    # It is not OpenVINO AUTO, and does not silently choose an installed GPU.
    backend = 'openvino-gpu' if performance.backend == 'intel-gpu' else performance.cpu_runtime
    accurate = performance.mode == 'accurate'
    return RuntimePlan(performance.backend, backend, 2 if accurate else performance.cpu_threads,
                       'seek' if accurate else 'sequential', 'fast' if performance.mode == 'fast' else 'accurate')
