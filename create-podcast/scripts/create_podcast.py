#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path

import requests


DEFAULT_MODEL = "gpt-5.4"
DEFAULT_ENDPOINT = "https://api.openai.com/v1/responses"
SCRIPT_DIR = Path(__file__).resolve().parent
RENDER_SCRIPT = SCRIPT_DIR / "render_podcast.py"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a two-presenter podcast script from a text file and render audio."
    )
    parser.add_argument("input_path", help="Path to the source text file.")
    parser.add_argument(
        "--output-dir",
        help="Directory for generated files. Defaults to the input file directory.",
    )
    parser.add_argument(
        "--script-path",
        help="Explicit path for the generated podcast script file.",
    )
    parser.add_argument(
        "--audio-path",
        help="Explicit path for the rendered audio file.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model used to generate the podcast script. Defaults to {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("OPENAI_RESPONSES_ENDPOINT", DEFAULT_ENDPOINT),
        help="Responses API endpoint. Defaults to the standard OpenAI endpoint.",
    )
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable containing the API key.",
    )
    parser.add_argument(
        "--presenter-a",
        default="Presenter 1",
        help="Speaker label for the first presenter.",
    )
    parser.add_argument(
        "--presenter-b",
        default="Presenter 2",
        help="Speaker label for the second presenter.",
    )
    parser.add_argument("--voice-a", help="Voice passed through to the renderer for presenter A.")
    parser.add_argument("--voice-b", help="Voice passed through to the renderer for presenter B.")
    parser.add_argument(
        "--tts-tool",
        choices=["auto", "edge-tts", "espeak-ng", "espeak"],
        default="auto",
        help="TTS backend passed through to render_podcast.py.",
    )
    parser.add_argument(
        "--pause-ms",
        type=int,
        default=350,
        help="Pause between turns for WAV rendering backends.",
    )
    parser.add_argument(
        "--audio-format",
        choices=["wav", "mp3"],
        default="wav",
        help="Audio file extension to generate.",
    )
    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="Generate the script file only.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    return parser.parse_args()


def read_source_text(input_path):
    path = Path(input_path).expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Input file not found: {path}")
    return path, path.read_text(encoding="utf-8")


def derive_output_paths(source_path, output_dir, script_path, audio_path, audio_format):
    if output_dir:
        base_dir = Path(output_dir).expanduser().resolve()
    else:
        base_dir = source_path.parent

    base_dir.mkdir(parents=True, exist_ok=True)
    stem = source_path.stem

    script_out = (
        Path(script_path).expanduser().resolve()
        if script_path
        else base_dir / f"{stem}.podcast-script.md"
    )
    audio_out = (
        Path(audio_path).expanduser().resolve()
        if audio_path
        else base_dir / f"{stem}.podcast.{audio_format}"
    )

    return script_out, audio_out


def ensure_writable(path, overwrite):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise SystemExit(f"Refusing to overwrite existing file without --overwrite: {path}")


def build_instructions(presenter_a, presenter_b):
    return f"""Convert source material into a podcast-ready script for exactly two presenters.

Rules:
- Output only the final script with no markdown fences or commentary.
- Use exactly these speaker labels: {presenter_a}: and {presenter_b}:
- Keep each turn on its own labeled line or paragraph so it is ready for TTS parsing.
- If the source is conversational, preserve the original sequence, themes, and phrasing as closely as possible, changing only what is needed for clarity, pacing, and listenability.
- If the source is expository, convert it into a content-dense exchange between the two presenters without adding unsupported facts or empty banter.
- Remove citations, footnotes, and formatting that do not belong in spoken audio unless they are essential to meaning.
- Do not invent facts, quotes, events, or claims not present in the source.
"""


def build_input_prompt(source_path, source_text, presenter_a, presenter_b):
    return f"""Create a two-presenter podcast script from the following source file.

Source file: {source_path.name}
Presenter names:
- {presenter_a}
- {presenter_b}

Source text:
<<<SOURCE
{source_text}
SOURCE
"""


def call_responses_api(endpoint, api_key, model, instructions, input_text):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if os.environ.get("OPENAI_ORGANIZATION"):
        headers["OpenAI-Organization"] = os.environ["OPENAI_ORGANIZATION"]
    if os.environ.get("OPENAI_PROJECT"):
        headers["OpenAI-Project"] = os.environ["OPENAI_PROJECT"]

    payload = {
        "model": model,
        "instructions": instructions,
        "input": input_text,
        "text": {"format": {"type": "text"}},
        "temperature": 0.3,
    }

    response = requests.post(endpoint, headers=headers, json=payload, timeout=300)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text.strip()
        message = f"Responses API request failed with status {response.status_code}."
        if detail:
            message = f"{message}\n{detail}"
        raise SystemExit(message) from exc

    return response.json()


def extract_output_text(response_json):
    if isinstance(response_json.get("output_text"), str) and response_json["output_text"].strip():
        return response_json["output_text"].strip()

    output_items = response_json.get("output", [])
    chunks = []
    for item in output_items:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                chunks.append(content["text"])

    text = "\n".join(chunks).strip()
    if text:
        return text
    raise SystemExit("Responses API did not return any usable output text.")


def normalize_script(script_text):
    cleaned = script_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        lines = cleaned.splitlines()
        if lines and not lines[0].startswith("Presenter"):
            lines = lines[1:]
        cleaned = "\n".join(lines).strip()
    return cleaned + "\n"


def render_audio(script_path, audio_path, args):
    cmd = [
        "python3",
        str(RENDER_SCRIPT),
        str(script_path),
        "--output",
        str(audio_path),
        "--tool",
        args.tts_tool,
        "--pause-ms",
        str(args.pause_ms),
    ]
    if args.voice_a:
        cmd.extend(["--voice-a", args.voice_a])
    if args.voice_b:
        cmd.extend(["--voice-b", args.voice_b])
    subprocess.run(cmd, check=True)


def main():
    args = parse_args()
    source_path, source_text = read_source_text(args.input_path)
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(
            f"Missing API key. Export {args.api_key_env} before running this command."
        )

    script_path, audio_path = derive_output_paths(
        source_path,
        args.output_dir,
        args.script_path,
        args.audio_path,
        args.audio_format,
    )
    ensure_writable(script_path, overwrite=args.overwrite)
    if not args.skip_audio:
        ensure_writable(audio_path, overwrite=args.overwrite)

    instructions = build_instructions(args.presenter_a, args.presenter_b)
    input_text = build_input_prompt(
        source_path,
        source_text,
        args.presenter_a,
        args.presenter_b,
    )
    response_json = call_responses_api(
        args.endpoint,
        api_key,
        args.model,
        instructions,
        input_text,
    )
    script_text = normalize_script(extract_output_text(response_json))
    script_path.write_text(script_text, encoding="utf-8")
    print(f"Saved podcast script: {script_path}")

    if args.skip_audio:
        return

    try:
        render_audio(script_path, audio_path, args)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc

    print(f"Saved podcast audio: {audio_path}")


if __name__ == "__main__":
    main()
