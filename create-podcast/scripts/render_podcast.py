#!/usr/bin/env python3
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path


EDGE_DEFAULT_VOICE_A = "en-US-AndrewMultilingualNeural"
EDGE_DEFAULT_VOICE_B = "en-US-AvaMultilingualNeural"
ESPEAK_DEFAULT_VOICE_A = "en-us+m3"
ESPEAK_DEFAULT_VOICE_B = "en-us+f2"
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
VENV_BIN = SKILL_ROOT / ".venv" / "bin"
VENV_PYTHON = VENV_BIN / "python"
LOCAL_EDGE_TTS = VENV_BIN / "edge-tts"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render a two-speaker podcast script into a single audio file."
    )
    parser.add_argument("script_path", help="Path to the podcast script file.")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to the rendered audio file. Use .wav for espeak output or .mp3 for edge-tts output.",
    )
    parser.add_argument(
        "--tool",
        choices=["auto", "edge-tts", "espeak-ng", "espeak"],
        default="auto",
        help="TTS backend to use. Defaults to auto-detection.",
    )
    parser.add_argument("--voice-a", help="Voice for the first speaker.")
    parser.add_argument("--voice-b", help="Voice for the second speaker.")
    parser.add_argument(
        "--rate-a",
        default="+0%",
        help="Speaking rate for the first speaker when using edge-tts.",
    )
    parser.add_argument(
        "--rate-b",
        default="-8%",
        help="Speaking rate for the second speaker when using edge-tts.",
    )
    parser.add_argument(
        "--pitch-a",
        default="+0Hz",
        help="Pitch for the first speaker when using edge-tts.",
    )
    parser.add_argument(
        "--pitch-b",
        default="+2Hz",
        help="Pitch for the second speaker when using edge-tts.",
    )
    parser.add_argument(
        "--volume-a",
        default="+0%",
        help="Volume for the first speaker when using edge-tts.",
    )
    parser.add_argument(
        "--volume-b",
        default="+0%",
        help="Volume for the second speaker when using edge-tts.",
    )
    parser.add_argument(
        "--pause-ms",
        type=int,
        default=350,
        help="Silence inserted between turns when rendering WAV output.",
    )
    return parser.parse_args()


def resolve_edge_tts_executable():
    edge_tts = shutil.which("edge-tts")
    if edge_tts:
        return edge_tts
    if LOCAL_EDGE_TTS.exists():
        return str(LOCAL_EDGE_TTS)
    return None


def resolve_ffmpeg_executable():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg

    if VENV_PYTHON.exists():
        try:
            result = subprocess.run(
                [
                    str(VENV_PYTHON),
                    "-c",
                    "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            return None

        candidate = result.stdout.strip()
        if candidate and Path(candidate).exists():
            return candidate

    return None


def detect_tool(requested):
    if requested != "auto":
        if requested == "edge-tts" and resolve_edge_tts_executable():
            return requested
        if shutil.which(requested):
            return requested
        raise SystemExit(f"Requested TTS tool '{requested}' is not available on PATH.")

    if resolve_edge_tts_executable() and resolve_ffmpeg_executable():
        return "edge-tts"
    if shutil.which("espeak-ng"):
        return "espeak-ng"
    if shutil.which("espeak"):
        return "espeak"

    raise SystemExit(
        "No supported TTS CLI found. Install edge-tts with ffmpeg, espeak-ng, or espeak."
    )


def parse_script(script_path):
    lines = Path(script_path).read_text(encoding="utf-8").splitlines()
    turns = []
    current_speaker = None
    current_parts = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^([^:]{1,80}):\s*(.+)$", line)
        if match:
            if current_speaker and current_parts:
                turns.append((current_speaker, " ".join(current_parts).strip()))
            current_speaker = match.group(1).strip()
            current_parts = [match.group(2).strip()]
        elif current_speaker:
            current_parts.append(line)

    if current_speaker and current_parts:
        turns.append((current_speaker, " ".join(current_parts).strip()))

    if not turns:
        raise SystemExit(
            "Could not parse any speaker turns. Use 'Speaker: text' lines in the script."
        )

    speakers = []
    for speaker, _ in turns:
        if speaker not in speakers:
            speakers.append(speaker)

    if len(speakers) > 2:
        raise SystemExit(
            f"Expected at most two speakers, found {len(speakers)}: {', '.join(speakers)}"
        )

    return turns, speakers


def ensure_parent(path_str):
    Path(path_str).parent.mkdir(parents=True, exist_ok=True)


def render_edge_tts(
    turns,
    speakers,
    output_path,
    voice_a=None,
    voice_b=None,
    rate_a="+0%",
    rate_b="-8%",
    pitch_a="+0Hz",
    pitch_b="+2Hz",
    volume_a="+0%",
    volume_b="+0%",
):
    edge_tts_exe = resolve_edge_tts_executable()
    ffmpeg_exe = resolve_ffmpeg_executable()
    if not edge_tts_exe or not ffmpeg_exe:
        raise SystemExit("edge-tts rendering requires ffmpeg to merge speaker segments.")

    voice_map = {}
    rate_map = {}
    pitch_map = {}
    volume_map = {}
    if speakers:
        voice_map[speakers[0]] = voice_a or EDGE_DEFAULT_VOICE_A
        rate_map[speakers[0]] = rate_a
        pitch_map[speakers[0]] = pitch_a
        volume_map[speakers[0]] = volume_a
    if len(speakers) > 1:
        voice_map[speakers[1]] = voice_b or EDGE_DEFAULT_VOICE_B
        rate_map[speakers[1]] = rate_b
        pitch_map[speakers[1]] = pitch_b
        volume_map[speakers[1]] = volume_b

    ensure_parent(output_path)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        segment_paths = []

        for index, (speaker, text) in enumerate(turns, start=1):
            segment_path = temp_root / f"segment-{index:03d}.mp3"
            voice = voice_map.get(speaker, voice_a or EDGE_DEFAULT_VOICE_A)
            rate = rate_map.get(speaker, rate_a)
            pitch = pitch_map.get(speaker, pitch_a)
            volume = volume_map.get(speaker, volume_a)
            cmd = [
                edge_tts_exe,
                "--voice",
                voice,
                f"--rate={rate}",
                f"--pitch={pitch}",
                f"--volume={volume}",
                "--text",
                text,
                "--write-media",
                str(segment_path),
            ]
            subprocess.run(cmd, check=True)
            segment_paths.append(segment_path)

        concat_file = temp_root / "segments.txt"
        concat_file.write_text(
            "".join(f"file '{segment_path}'\n" for segment_path in segment_paths),
            encoding="utf-8",
        )

        cmd = [
            ffmpeg_exe,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
        ]

        if Path(output_path).suffix.lower() == ".mp3":
            cmd.extend(["-c", "copy"])
        elif Path(output_path).suffix.lower() == ".wav":
            cmd.extend(["-acodec", "pcm_s16le"])

        cmd.append(output_path)
        subprocess.run(cmd, check=True)


def render_espeak(turns, speakers, output_path, tool_name, voice_a=None, voice_b=None, pause_ms=350):
    voice_map = {}
    if speakers:
        voice_map[speakers[0]] = voice_a or ESPEAK_DEFAULT_VOICE_A
    if len(speakers) > 1:
        voice_map[speakers[1]] = voice_b or ESPEAK_DEFAULT_VOICE_B

    ensure_parent(output_path)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        segment_paths = []

        for index, (speaker, text) in enumerate(turns, start=1):
            segment_path = temp_root / f"segment-{index:03d}.wav"
            voice = voice_map.get(speaker, voice_a or ESPEAK_DEFAULT_VOICE_A)
            cmd = [tool_name, "-w", str(segment_path), "-v", voice, text]
            subprocess.run(cmd, check=True)
            segment_paths.append(segment_path)

        concatenate_wavs(segment_paths, output_path, pause_ms=pause_ms)


def concatenate_wavs(segment_paths, output_path, pause_ms=350):
    with wave.open(str(segment_paths[0]), "rb") as first:
        params = first.getparams()
        frame_rate = first.getframerate()
        silence_frames = int(frame_rate * (pause_ms / 1000.0))
        silence = b"\x00" * silence_frames * params.sampwidth * params.nchannels

    with wave.open(output_path, "wb") as out_file:
        out_file.setparams(
            (
                params.nchannels,
                params.sampwidth,
                params.framerate,
                0,
                params.comptype,
                params.compname,
            )
        )
        for index, segment_path in enumerate(segment_paths):
            with wave.open(str(segment_path), "rb") as in_file:
                current_params = in_file.getparams()
                if (
                    current_params.nchannels != params.nchannels
                    or current_params.sampwidth != params.sampwidth
                    or current_params.framerate != params.framerate
                    or current_params.comptype != params.comptype
                    or current_params.compname != params.compname
                ):
                    raise SystemExit("WAV parameters did not match across rendered segments.")
                out_file.writeframes(in_file.readframes(in_file.getnframes()))
            if index < len(segment_paths) - 1 and silence:
                out_file.writeframes(silence)


def main():
    args = parse_args()
    turns, speakers = parse_script(args.script_path)
    tool = detect_tool(args.tool)

    if tool == "edge-tts":
        render_edge_tts(
            turns,
            speakers,
            args.output,
            voice_a=args.voice_a,
            voice_b=args.voice_b,
            rate_a=args.rate_a,
            rate_b=args.rate_b,
            pitch_a=args.pitch_a,
            pitch_b=args.pitch_b,
            volume_a=args.volume_a,
            volume_b=args.volume_b,
        )
    else:
        render_espeak(
            turns,
            speakers,
            args.output,
            tool_name=tool,
            voice_a=args.voice_a,
            voice_b=args.voice_b,
            pause_ms=args.pause_ms,
        )

    print(f"Rendered podcast audio with {tool}: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"TTS command failed: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc
