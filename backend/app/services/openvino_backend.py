"""Optional OpenVINO adapter for the installed RapidOCR 1.4.4 stage interface.

Retains RapidOCR's preprocessing, CTC alphabet and postprocessing. Compiles the
same bundled ONNX models; device selection is explicit, never OpenVINO AUTO.
"""
from pathlib import Path


class OpenVINOSession:
    def __init__(self, core, model: Path, device: str, threads: int):
        import openvino as ov
        config = {'PERFORMANCE_HINT': 'LATENCY', 'INFERENCE_PRECISION_HINT': 'f32', 'NUM_STREAMS': '1'}
        if device == 'CPU':
            config['INFERENCE_NUM_THREADS'] = threads
        self.compiled = core.compile_model(core.read_model(model), device, config)
        self.devices = list(self.compiled.get_property('EXECUTION_DEVICES'))
        if not self.devices or any(not actual.startswith(device) for actual in self.devices):
            raise RuntimeError(f'Expected {device} execution, got {self.devices}. No silent device fallback is allowed.')
        self.request = self.compiled.create_infer_request()

    def __call__(self, image):
        self.request.start_async({self.compiled.input(0): image}, share_inputs=False)
        self.request.wait()
        # Outputs must survive the next infer_request call, just like ORT arrays.
        return [self.request.get_output_tensor(index).data.copy() for index in range(len(self.compiled.outputs))]


def replace_sessions(engine, backend: str, threads: int):
    if backend not in ('openvino-cpu', 'openvino-gpu'):
        raise ValueError(f'Unknown OCR backend: {backend}')
    try:
        import openvino as ov
    except ImportError as exc:
        raise RuntimeError('OpenVINO is not installed. Install backend/requirements-openvino.txt with the project Python, then restart. CPU OCR remains available.') from exc
    import rapidocr_onnxruntime
    core = ov.Core()
    device = 'GPU' if backend == 'openvino-gpu' else 'CPU'
    if device not in core.available_devices:
        raise RuntimeError(f'OpenVINO {device} is unavailable. Discovered devices: {core.available_devices}. Select CPU; no driver is installed automatically.')
    folder = Path(rapidocr_onnxruntime.__file__).parent / 'models'
    detection = OpenVINOSession(core, folder / 'ch_PP-OCRv4_det_infer.onnx', device, threads)
    recognition = OpenVINOSession(core, folder / 'ch_PP-OCRv4_rec_infer.onnx', device, threads)
    engine.text_det.infer = detection
    engine.text_rec.session = recognition
    return {'detection': ','.join(detection.devices), 'recognition': ','.join(recognition.devices),
            'classification': 'disabled', 'runtime': f'OpenVINO {ov.__version__}',
            'device_name': core.get_property(device, 'FULL_DEVICE_NAME'), 'precision': 'f32', 'streams': 1, 'fallback': False}
