"""Export all individual benchmark runs and medians without discarding slow runs."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def summarize():
    rows = []
    for path in sorted((ROOT / 'data/ocr-bench').glob('*.json')):
        document = json.loads(path.read_text(encoding='utf-8'))
        if 'runs' not in document:
            continue
        for run in document['runs']:
            quality = run.get('quality', {})
            rows.append(dict(experiment=path.stem, kind=run['kind'], repetition=run['repetition'],
                             seconds=run['processing_seconds'], initialization=run['initialization_seconds'],
                             end_to_end=run['end_to_end_seconds'], warm_median=document['warm_median_seconds'],
                             sampled_frames=run['frames'], ocr_passes=run['ocr_calls'], reused_frames=run['reused_frames'],
                             segments=len(run['segments']), peak_process_mib=run['process_lifetime_peak_memory_mib'],
                             exact_text_and_times=quality.get('exact_text_and_times', ''), false_reuse=len(quality.get('false_reuse_indices', [])),
                             **{f'seconds_{key}': run['timings'].get(key, '') for key in ['decode', 'preprocessing', 'detection_inference',
                                'recognition_inference', 'primary_pass', 'fallback_pass', 'ocr_postprocessing', 'merging', 'database', 'change_detection']}))
    output = ROOT / 'docs/OCR_PERFORMANCE_RESULTS.csv'
    with output.open('w', newline='', encoding='utf-8') as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(output)


if __name__ == '__main__':
    summarize()
