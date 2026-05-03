# LLM Skills

A collection of reusable Codex/LLM skills and helper scripts for common content workflows.

## Repository structure

- `transcribe/`
  - `SKILL.md`: Skill instructions for audio transcription workflows.
- `transcribe-codex/`
  - `SKILL.md`: Codex-focused transcription skill guidance.
- `create-podcast/`
  - `SKILL.md`: Skill instructions for generating podcasts.
  - `agents/openai.yaml`: Agent configuration used by the podcast workflow.
  - `scripts/create_podcast.py`: Main script for podcast generation.
  - `scripts/render_podcast.py`: Rendering/post-processing helper for podcast output.
  - `scripts/install_tts_ubuntu.sh`: Ubuntu setup script for TTS dependencies.
  - `scripts/install_edge_tts_local.sh`: Local Edge TTS setup helper.

## Getting started

1. Read the relevant `SKILL.md` for the workflow you want to run.
2. Install dependencies required by that skill/script.
3. Run the associated script(s) from the `create-podcast/scripts` folder when needed.

## Notes

- This repo is organized around skill definitions (`SKILL.md`) plus supporting scripts.
- Check each skill's instructions before running scripts, since requirements may vary.

## License

This project is licensed under the terms in `LICENSE`.
