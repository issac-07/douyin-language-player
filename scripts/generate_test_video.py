"""Generate original synthetic media. No downloaded footage, audio, or subtitle results."""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "fixtures" / "mandarin-test.mp4"
CAPTIONS = """1
00:00:00,500 --> 00:00:02,500
今天我们一起去吃饭

2
00:00:03,000 --> 00:00:05,000
你在干什么？

3
00:00:05,500 --> 00:00:07,500
我不知道发生了什么
"""


def generate(output: Path = DEFAULT_OUTPUT) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is required to generate the test fixture. Add it to PATH.")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dlp-fixture-") as directory:
        Path(directory, "captions.srt").write_text(CAPTIONS, encoding="utf-8")
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=24:duration=8",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=8",
            "-vf", "subtitles=captions.srt:force_style='Fontname=Microsoft YaHei,Fontsize=20,MarginV=35,Outline=2'",
            "-c:v", "libx264", "-preset", "fast", "-crf", "26", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", "-shortest", str(output),
        ], cwd=directory, check=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    print(generate(arguments.output))
