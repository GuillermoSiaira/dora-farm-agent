"""Edit the DORA demo video from the takes recorded by record.py.

  .venv/Scripts/python.exe infra/video/edit.py            # build out/dora-demo.mp4
  .venv/Scripts/python.exe infra/video/edit.py --voice    # (re)generate the narration first

For each scene of SCENES: cut the take by its markers, play typing and reading at
real speed, speed up the model's waits (with a badge that says how long it really
took), add the English narration (Amazon Polly) and burned-in English subtitles.
Every frame on screen comes from the real app; nothing is mocked.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
BUILD = OUT / "build"
VOICE_DIR = OUT / "voice"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 1920, 1080, 30
FONT = "C:/Windows/Fonts/segoeui.ttf"
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
GREEN = (34, 197, 94)
DARK = (17, 24, 39)

POLLY_VOICE = "Matthew"
POLLY_ENGINE = "generative"


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(" ".join(cmd)[:600])
        print(r.stderr[-3000:])
        raise SystemExit(1)


def duration(path: Path) -> float:
    r = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True, errors="replace")
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"no duration for {path}")


# ----------------------------------------------------------------------------
# Takes
# ----------------------------------------------------------------------------

class Take:
    def __init__(self, name: str):
        folders = sorted(p for p in OUT.glob(f"{name}_2*") if (p / "markers.json").exists()
                         and json.loads((p / "markers.json").read_text(encoding="utf-8")).get("ok"))
        if not folders:
            raise SystemExit(f"no good take for {name}")
        self.dir = folders[-1]
        self.frames = json.loads((self.dir / "frames.json").read_text(encoding="utf-8"))
        self.markers = json.loads((self.dir / "markers.json").read_text(encoding="utf-8"))["markers"]
        print(f"take {name}: {self.dir.name}, {len(self.frames)} frames")

    def t(self, scene, event, nth: int = 0) -> float:
        hits = [m["t"] for m in self.markers if m["scene"] == scene and m["event"] == event]
        if len(hits) <= nth:
            raise KeyError(f"{self.dir.name}: no marker {scene}/{event}#{nth}")
        return hits[nth]

    def all(self, scene, event) -> list[dict]:
        return [m for m in self.markers if m["scene"] == scene and m["event"] == event]

    def clip(self, t0: float, t1: float, out: Path, speed: float = 1.0) -> Path:
        """Frames between t0 and t1 (absolute clock) as a CFR mp4, sped up by `speed`."""
        fr = self.frames
        idx = [i for i, f in enumerate(fr) if t0 <= f["t"] < t1]
        before = [i for i, f in enumerate(fr) if f["t"] < t0]
        if before:
            idx = [before[-1]] + idx
        if not idx:
            raise RuntimeError(f"no frames in {t0}-{t1}")
        # One output frame every 1/FPS s of output time: the last capture at or
        # before the matching source time. Deterministic, unlike concat durations.
        n_out = max(1, round((t1 - t0) / speed * FPS))
        proc = subprocess.Popen(
            [FFMPEG, "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
             "-vf", f"scale={W}:{H}:flags=lanczos,format=yuv420p",
             "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-an", str(out)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        j, cache = 0, {}
        for n in range(n_out):
            ts = t0 + n * speed / FPS
            while j + 1 < len(idx) and fr[idx[j + 1]]["t"] <= ts:
                j += 1
            name = fr[idx[j]]["file"]
            if name not in cache:
                cache = {name: (self.dir / "frames" / name).read_bytes()}
            proc.stdin.write(cache[name])
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed on {out}")
        return out


# ----------------------------------------------------------------------------
# Graphics
# ----------------------------------------------------------------------------

def font(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def badge_png(text: str, out: Path) -> Path:
    f = font(30, True)
    pad = 18
    box = ImageDraw.Draw(Image.new("RGBA", (10, 10))).textbbox((0, 0), text, font=f)
    w, h = box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=(17, 24, 39, 225))
    d.text((pad, pad - box[1]), text, font=f, fill=(255, 255, 255, 255))
    img.save(out)
    return out


def label_png(text: str, out: Path) -> Path:
    """Top-left scene label, e.g. 'Spanish · Muse Spark 1.3 (Meta API)'."""
    f = font(34, True)
    pad = 20
    box = ImageDraw.Draw(Image.new("RGBA", (10, 10))).textbbox((0, 0), text, font=f)
    w, h = box[2] - box[0] + 2 * pad + 14, box[3] - box[1] + 2 * pad
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=12, fill=(255, 255, 255, 240), outline=GREEN + (255,), width=3)
    d.rectangle((0, 12, 8, h - 12), fill=GREEN + (255,))
    d.text((pad + 10, pad - box[1]), text, font=f, fill=DARK + (255,))
    img.save(out)
    return out


def card_png(title: str, lines: list[str], out: Path, small: str = "") -> Path:
    img = Image.new("RGB", (W, H), (246, 247, 242))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 14), fill=GREEN)
    ft = font(110, True)
    tb = d.textbbox((0, 0), title, font=ft)
    y = 330 if lines else 440
    d.text(((W - (tb[2] - tb[0])) / 2, y), title, font=ft, fill=DARK)
    y += 170
    for i, line in enumerate(lines):
        fl = font(52 if i == 0 else 42, i == 0)
        lb = d.textbbox((0, 0), line, font=fl)
        d.text(((W - (lb[2] - lb[0])) / 2, y), line, font=fl, fill=(55, 65, 81) if i else DARK)
        y += 80
    if small:
        fs = font(30)
        sb = d.textbbox((0, 0), small, font=fs)
        d.text(((W - (sb[2] - sb[0])) / 2, H - 110), small, font=fs, fill=(107, 114, 128))
    img.save(out)
    return out


def still(png: Path, seconds: float, out: Path) -> Path:
    run([FFMPEG, "-y", "-loop", "1", "-t", f"{seconds:.3f}", "-i", str(png),
         "-vf", f"scale={W}:{H},fps={FPS},format=yuv420p", "-c:v", "libx264", "-crf", "16", str(out)])
    return out


def overlay(src: Path, png: Path, out: Path, x: str, y: str) -> Path:
    run([FFMPEG, "-y", "-i", str(src), "-i", str(png), "-filter_complex",
         f"[0:v][1:v]overlay={x}:{y},format=yuv420p", "-c:v", "libx264", "-crf", "16", str(out)])
    return out


def concat(parts: list[Path], out: Path) -> Path:
    lst = out.with_suffix(".txt")
    lst.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8")
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    return out


# ----------------------------------------------------------------------------
# Scene building blocks
# ----------------------------------------------------------------------------

@dataclass
class Seg:
    take: str
    t0: object          # absolute time, or (scene, event, nth[, offset])
    t1: object
    speed: float = 1.0
    badge: str = ""      # shown while the segment plays (sped-up waits)


@dataclass
class Scene:
    name: str
    narration: str
    segs: list[Seg] = field(default_factory=list)
    card: tuple | None = None       # (title, lines, small) for a title card
    label: str = ""                 # top-left label for the whole scene
    min_seconds: float = 0.0


TAKES: dict[str, Take] = {}


def take(name: str) -> Take:
    if name not in TAKES:
        TAKES[name] = Take(name)
    return TAKES[name]


def resolve(tk: Take, spec) -> float:
    if isinstance(spec, (int, float)):
        return float(spec)
    scene, event, nth, *off = spec
    return tk.t(scene, event, nth) + (off[0] if off else 0.0)


def wait(tk_name: str, scene, nth: int, target: float = 2.2, lang: str = "en") -> Seg:
    """The model's wait between 'sent' #nth and 'answer' #nth, squeezed to ~target s."""
    tk = take(tk_name)
    t0, t1 = tk.t(scene, "sent", nth), tk.t(scene, "answer", nth)
    real = t1 - t0
    speed = max(real / target, 1.0)
    return Seg(tk_name, t0, t1, speed, f"{speed:.0f}× faster   ·   DORA took {real:.0f} s")


# ----------------------------------------------------------------------------
# Narration
# ----------------------------------------------------------------------------

def make_voice(scenes: list[Scene]) -> None:
    import boto3
    polly = boto3.client("polly", region_name="us-east-1")
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    for sc in scenes:
        if not sc.narration:
            continue
        # The generative engine gives no speech marks: synthesize sentence by sentence,
        # join them with a short pause, and the sentence times are known exactly.
        import re as _re
        sentences = [s for s in _re.split(r"(?<=[.;:])\s+", sc.narration.strip()) if s]
        pieces, marks, t = [], [], 0.0
        for k, sent in enumerate(sentences):
            part = VOICE_DIR / f"{sc.name}_{k:02d}.mp3"
            r = polly.synthesize_speech(Text=sent, VoiceId=POLLY_VOICE, Engine=POLLY_ENGINE,
                                        OutputFormat="mp3", SampleRate="24000")
            part.write_bytes(r["AudioStream"].read())
            marks.append({"time": int(t * 1000), "value": sent})
            pieces.append(part)
            t += duration(part) + 0.25
        mp3 = VOICE_DIR / f"{sc.name}.mp3"
        inputs, chains = [], []
        for k, p in enumerate(pieces):
            inputs += ["-i", str(p)]
            chains.append(f"[{k}:a]aresample=48000,apad=pad_dur=0.25[a{k}]")
        mix = ";".join(chains) + ";" + "".join(f"[a{k}]" for k in range(len(pieces))) + \
            f"concat=n={len(pieces)}:v=0:a=1,loudnorm=I=-16:TP=-1.5[out]"
        run([FFMPEG, "-y", *inputs, "-filter_complex", mix, "-map", "[out]", "-ar", "48000",
             "-c:a", "libmp3lame", "-b:a", "192k", str(mp3)])
        (VOICE_DIR / f"{sc.name}.marks.json").write_text(json.dumps(marks, ensure_ascii=False), encoding="utf-8")
        print(f"voice {sc.name}: {duration(mp3):.1f} s, {len(sentences)} sentences")


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def split_caption(text: str, limit: int = 62) -> list[str]:
    words, chunks, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > limit and cur:
            chunks.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        chunks.append(cur)
    return chunks


# ----------------------------------------------------------------------------
# Build
# ----------------------------------------------------------------------------

VOICE_LEAD = 0.4   # seconds of picture before the voice starts in each scene
TAIL = 0.4         # seconds after the voice ends


def build_scene(i: int, sc: Scene) -> tuple[Path, float]:
    BUILD.mkdir(parents=True, exist_ok=True)
    parts = []
    if sc.card:
        title, lines, small = sc.card
        parts.append(still(card_png(title, lines, BUILD / f"{i:02d}_card.png", small), 2.5, BUILD / f"{i:02d}_card.mp4"))
    for k, s in enumerate(sc.segs):
        tk = take(s.take)
        clip = tk.clip(resolve(tk, s.t0), resolve(tk, s.t1), BUILD / f"{i:02d}_{k:02d}.mp4", s.speed)
        if s.badge:
            clip = overlay(clip, badge_png(s.badge, BUILD / f"{i:02d}_{k:02d}_b.png"),
                           BUILD / f"{i:02d}_{k:02d}_b.mp4", "W-w-40", "H-h-150")
        parts.append(clip)
    video = concat(parts, BUILD / f"{i:02d}_video.mp4") if len(parts) > 1 else parts[0]
    if sc.label:
        video = overlay(video, label_png(sc.label, BUILD / f"{i:02d}_label.png"),
                        BUILD / f"{i:02d}_lab.mp4", "36", "28")

    vdur = duration(video)
    mp3 = VOICE_DIR / f"{sc.name}.mp3"
    adur = duration(mp3) if mp3.exists() else 0.0
    total = max(vdur, VOICE_LEAD + adur + TAIL, sc.min_seconds)
    pad = total - vdur
    out = BUILD / f"{i:02d}_{sc.name}.mp4"
    inputs = [FFMPEG, "-y", "-i", str(video)]
    if mp3.exists():
        inputs += ["-i", str(mp3)]
        a = (f"[1:a]adelay={int(VOICE_LEAD * 1000)}|{int(VOICE_LEAD * 1000)},"
             f"apad,atrim=0:{total:.3f},aresample=48000,aformat=channel_layouts=stereo[a]")
    else:
        inputs += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        a = f"[1:a]atrim=0:{total:.3f}[a]"
    v = f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.3f},trim=0:{total:.3f},setpts=PTS-STARTPTS[v]"
    run(inputs + ["-filter_complex", f"{v};{a}", "-map", "[v]", "-map", "[a]",
                  "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", str(out)])
    print(f"scene {i:02d} {sc.name}: video {vdur:.1f} s, voice {adur:.1f} s -> {total:.1f} s")
    return out, total


def build(scenes: list[Scene], out: Path) -> None:
    parts, srt, clock = [], [], 0.0
    n = 1
    for i, sc in enumerate(scenes):
        path, total = build_scene(i, sc)
        parts.append(path)
        marks = VOICE_DIR / f"{sc.name}.marks.json"
        if marks.exists():
            ms = json.loads(marks.read_text(encoding="utf-8"))
            adur = duration(VOICE_DIR / f"{sc.name}.mp3")
            for j, m in enumerate(ms):
                s0 = m["time"] / 1000
                s1 = ms[j + 1]["time"] / 1000 if j + 1 < len(ms) else adur
                chunks = split_caption(m["value"])
                step = (s1 - s0) / len(chunks)
                for c, text in enumerate(chunks):
                    a = clock + VOICE_LEAD + s0 + c * step
                    srt.append(f"{n}\n{srt_time(a)} --> {srt_time(a + step - 0.05)}\n{text}\n")
                    n += 1
        clock += total
    joined = concat(parts, BUILD / "joined.mp4")
    (BUILD / "subs.srt").write_text("\n".join(srt), encoding="utf-8")
    if not srt:
        run([FFMPEG, "-y", "-i", str(joined), "-c", "copy", "-movflags", "+faststart", str(out)])
        print(f"done (no voice): {out} ({clock:.1f} s)")
        return
    style = ("FontName=Segoe UI,FontSize=17,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
             "BackColour=&H99000000,BorderStyle=4,Outline=0,Shadow=0,MarginV=26,Bold=1")
    subprocess.run([FFMPEG, "-y", "-i", "joined.mp4", "-vf", f"subtitles=subs.srt:force_style='{style}'",
                    "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-c:a", "copy",
                    "-movflags", "+faststart", str(out.resolve())],
                   cwd=BUILD, check=True, capture_output=True)
    print(f"done: {out} ({clock:.1f} s)")


def main() -> None:
    from scenes import SCENES  # the cut list lives next to this file
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", action="store_true", help="generate the narration with Amazon Polly")
    ap.add_argument("--only", type=int, nargs="*", help="build only these scene numbers (preview)")
    ap.add_argument("--out", default=str(OUT / "dora-demo.mp4"))
    args = ap.parse_args()
    scenes = SCENES()
    if args.voice:
        make_voice(scenes)
    if args.only:
        for i in args.only:
            build_scene(i, scenes[i])
        return
    build(scenes, Path(args.out))


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main()
