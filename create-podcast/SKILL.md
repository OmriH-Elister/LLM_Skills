---
name: create-podcast
description: Transform user-provided text or text files into a two-presenter podcast script, save the script to a separate file, and render the script into audio with the best available local TTS CLI. Use when Codex needs to turn essays, notes, transcripts, interviews, chats, or conversations into a podcast-ready script and audio file, especially when a source conversation should be preserved as closely as possible while making only the changes needed for a listenable podcast.
---

# Create Podcast

## Workflow

1. Read the source text from the user message or the referenced file.
2. Classify the source as either conversational or expository.
3. Rewrite it into a two-presenter script that is ready for text-to-speech.
4. Save the script to a separate file before producing audio.
5. Prefer the one-command wrapper `scripts/create_podcast.py` when the user wants file-to-script-to-audio automation.
6. Render audio with `scripts/render_podcast.py` when the script already exists.
7. Report the output paths and any TTS limitations clearly.

## Rewriting Rules

- Use exactly two speakers unless the user explicitly supplies presenter names.
- Default speaker labels to `Presenter 1:` and `Presenter 2:`.
- Keep the final script as spoken prose. Remove markdown structure, citations, and stage directions unless the user asks to keep them.
- Do not invent facts, examples, or claims that are not supported by the source.
- Add only the minimum connective language needed to make the result sound coherent when spoken aloud.
- Prefer short paragraphs and natural turn-taking over dense monologues.
- Keep each spoken block on its own labeled line or paragraph so it can be parsed by the TTS renderer.

### Conversational Sources

- Preserve the original sequence, themes, and phrasing as closely as possible.
- Keep strong original lines when they already sound natural when spoken.
- Change only what is needed for clarity, pacing, or consistent speaker identification.
- If the source already alternates between two speakers, preserve that alternation.
- If the transcript includes filler or repetition that makes the audio hard to follow, trim lightly without changing the meaning.

### Expository Sources

- Split the material into a conversational exchange between two presenters.
- Use `Presenter 1` for setup, structure, and major takeaways.
- Use `Presenter 2` for questions, reactions, contrast, and clarifications.
- Do not add empty banter. Keep the dialogue content-dense and faithful to the source.
- When needed, add brief transitions at section boundaries so the audio flows cleanly.

## Output Rules

- Save the podcast script to a separate file and do not overwrite the source file unless the user explicitly asks for that.
- If the source came from a file like `filename.md`, default the script output to `filename.podcast-script.md`.
- Default the audio output to the same basename with a `.wav` suffix, for example `filename.podcast.wav`.
- If the user provides raw text instead of a file, save outputs in the current working directory with a concise descriptive basename.
- Make the saved script file the source of truth for audio rendering.

## Audio Rendering

- For a one-command file-to-script-to-audio flow, use:

```bash
python3 <CODEX_SKILLS_DIR>/create-podcast/scripts/create_podcast.py \
  path/to/input.txt
```

- Use `python3 <CODEX_SKILLS_DIR>/create-podcast/scripts/render_podcast.py <script-path> --output <audio-path>`.
- The renderer auto-selects the best supported local CLI in this order:
  `edge-tts` with `ffmpeg`, then `espeak-ng`, then `espeak`.
- The recommended quality path is a local `edge-tts` install inside the skill:

```bash
bash <CODEX_SKILLS_DIR>/create-podcast/scripts/install_edge_tts_local.sh
```

- That installer sets up a skill-local virtualenv with `edge-tts` and a bundled `ffmpeg`, and the renderer auto-detects both.
- On Ubuntu, install the recommended local backend with:

```bash
bash <CODEX_SKILLS_DIR>/create-podcast/scripts/install_tts_ubuntu.sh
```

- If the user specifies voices, pass them with `--voice-a` and `--voice-b`.
- If no supported TTS CLI is installed, still save the script file and state clearly that audio could not be produced on this machine.
- Keep the script in a simple speaker format that the renderer can parse:

```text
Presenter 1: Opening line.
Presenter 2: Response line.
Presenter 1: Next line.
```

## Command Pattern

Generate the podcast script and audio in one step with:

```bash
python3 <CODEX_SKILLS_DIR>/create-podcast/scripts/create_podcast.py \
  path/to/source.txt
```

After writing the script file, render it with:

```bash
python3 <CODEX_SKILLS_DIR>/create-podcast/scripts/render_podcast.py \
  path/to/output.podcast-script.md \
  --output path/to/output.podcast.wav
```

## Example Triggers

- `Please read the file in filename.md and rewrite the transcribed conversation between me and the AI model to make it fitting as a podcast script and produce the podcast.`
- `Please use the create-podcast skill to create a podcast about the essay in filename.txt.`

## Resource

- `scripts/create_podcast.py`: Read a source text file, generate the two-presenter podcast script with the OpenAI Responses API, save the script automatically, and render audio in one command.
- `scripts/render_podcast.py`: Parse a two-speaker script, choose the best available local TTS CLI, and write a single audio file.
- `scripts/install_edge_tts_local.sh`: Install the higher-quality `edge-tts` path into a skill-local virtualenv without requiring system packages.
- `scripts/install_tts_ubuntu.sh`: Install the recommended Ubuntu TTS backend for this skill.
