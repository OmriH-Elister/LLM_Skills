---
name: transcribe
description: Scan Google Drive My Drive/Useful/Research/Recordings for untranscribed audio files, transcribe them verbatim using the OpenAI whisper API, format as a labelled dialogue, and upload the resulting .md files back to the same Drive folder.
---

# Transcribe

This skill was imported from a Claude skill. It assumes the Google Drive MCP tools referenced below are available in the current Codex environment; if they are not, stop and report that dependency clearly.

You are executing the transcription workflow. Follow these steps exactly and in order.

## Argument Handling — Selective vs. Full Mode

Check whether a filename argument was passed to this skill invocation (e.g. `/transcribe Recording_2-11-26_16.30.mp4`).

- **Selective mode** (argument provided): the argument is the exact filename of one audio file in the Recordings folder. Skip Steps 3–5. In Step 6, the work queue contains only that one file — look it up by name in the Recordings folder instead of scanning everything.
- **Full mode** (no argument): proceed through all steps as written — scan, diff, and process every untranscribed file.

Keep this distinction in mind throughout.

## Step 1 — Authenticate Google Drive

Load the Google Drive MCP tool schemas and authenticate if not already done. Use `mcp__claude_ai_Google_Drive__authenticate` if auth is needed, then `mcp__claude_ai_Google_Drive__complete_authentication` to finish the flow. If already authenticated, skip ahead.

## Step 2 — Locate the Recordings Folder

Use `mcp__claude_ai_Google_Drive__search_files` to find the target folder. The path is:

```text
My Drive > Useful > Research > Recordings
```

Search with a query like `name = 'Recordings' and mimeType = 'application/vnd.google-apps.folder'` and confirm it is the right folder by checking its parents. Note the folder ID — you will need it for all subsequent queries.

## Step 3 — List Audio Files

Search for audio files inside the Recordings folder using the folder ID from Step 2. Use `mimeType` contains queries or search by common audio extensions. Run separate searches if needed for each type:

- `audio/mpeg` (.mp3)
- `audio/mp4` / `video/mp4` (.m4a, .mp4)
- `audio/wav` / `audio/x-wav` (.wav)
- `audio/ogg` (.ogg)
- `audio/flac` (.flac)
- `audio/aac` (.aac)
- `audio/webm` / `video/webm` (.webm)

Collect all results into one list. For each file note: `id`, `name`, and `mimeType`.

## Step 4 — List Existing Transcripts

Search the same Recordings folder for `.md` files. Query example:

```text
'<folder_id>' in parents and name contains '.md'
```

The transcript naming convention is `<audio_filename>.md` — e.g., `interview.m4a` → `interview.m4a.md`. Build a set of existing transcript names by collecting every `.md` file's title from the results.

## Step 5 — Identify Untranscribed Files

For each audio file from Step 3, check if `<audio_filename>.md` (the full original filename with its extension, plus `.md`) exists in the transcript set from Step 4. Files with no matching transcript are the work queue. Report the full list to the user before proceeding — show which files will be transcribed and which are already done.

If the work queue is empty, report `All recordings already transcribed.` and stop.

## Step 6 — Download, Transcribe, Format, and Upload Each File

**Selective mode only:** before downloading, look up the target file by name in the Recordings folder:

```text
parentId = '<folder_id>' and title = '<argument_filename>'
```

If no result is returned, stop and report: `File "<argument_filename>" not found in the Recordings folder.`

If `<argument_filename>.md` already exists in the folder, stop and report: `Transcript already exists for "<argument_filename>". Use a different filename or delete the existing transcript first.`

Otherwise proceed with the single file as the work queue.

For each file in the work queue, execute the following sub-steps:

### 6a. Download the audio file locally

Use `mcp__claude_ai_Google_Drive__download_file_content` with the file's ID. The tool returns base64-encoded binary content saved to a cached file on disk. Extract and decode it:

```bash
mkdir -p /tmp/transcribe_work
jq -r '.content' <cached_tool_result_path> | base64 -d > /tmp/transcribe_work/<filename>
```

Verify the file exists and has a non-zero size before proceeding:

```bash
ls -lh /tmp/transcribe_work/<filename>
```

### 6b. Get the verbatim transcript via the Whisper API

Read the OpenAI API key from fabric's config:

```bash
OPENAI_API_KEY=$(grep OPENAI_API_KEY ~/.config/fabric/.env | cut -d= -f2)
```

Call the Whisper API directly via curl — `response_format=text` returns plain text with no JSON wrapper and no LLM post-processing:

```bash
curl -s https://api.openai.com/v1/audio/transcriptions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F model="whisper-1" \
  -F response_format="text" \
  -F file="@/tmp/transcribe_work/<filename>"
```

Capture stdout as the raw verbatim transcript. If the curl call fails or returns a JSON error object, retry once. If it fails again, log the error, skip this file, and continue to the next one.

### 6c. Format as a labelled dialogue

Take the raw transcript text and format it as a structured dialogue. You will do this yourself — do not call any external API. Apply the following rules:

- Identify speaker changes based on conversational cues: question/answer patterns, topic shifts, different speech styles, names mentioned in context, or any other signal in the text.
- Label each speaker sequentially as **Speaker A**, **Speaker B**, **Speaker C**, etc. Do not attempt to name the speakers unless a name is explicitly spoken and clearly refers to that speaker.
- Each speaker turn gets its own line in the format: `**Speaker X:** <their words>`
- Do not merge turns from the same speaker if there is an intervening turn from another speaker.
- If the recording appears to be a single speaker with no other voice, format it as a monologue under `**Speaker A:**` only.
- Preserve the verbatim wording — correct nothing, add nothing, omit nothing from what was transcribed.

### 6d. Build the Markdown file

Assemble the final document:

```markdown
# <original audio filename>

**Source:** <original audio filename>
**Transcribed:** <current date YYYY-MM-DD>
**Model:** whisper-1

---

<formatted dialogue from 6c>
```

The output filename must be `<original_audio_filename>.md` — i.e., append `.md` directly to the full audio filename including its original extension. Examples:

- `interview.m4a` → `interview.m4a.md`
- `Recording_2-11-26_16.30.mp4` → `Recording_2-11-26_16.30.mp4.md`

Save the file locally to `/tmp/transcribe_work/<audio_filename>.md`.

### 6e. Upload the .md to Google Drive

Use `mcp__claude_ai_Google_Drive__create_file` to upload the file into the Recordings folder (use the folder ID from Step 2):

- `title`: `<audio_filename>.md`
- `parentId`: the Recordings folder ID
- `textContent`: the full markdown content
- `contentMimeType`: `text/plain`
- `disableConversionToGoogleType`: `true`

Confirm the upload succeeded by checking the returned file ID.

### 6f. Clean up

Delete the local audio file and .md file after a successful upload:

```bash
rm /tmp/transcribe_work/<filename> /tmp/transcribe_work/<filename>.md
```

## Step 7 — Summary Report

After processing all files, output a summary table:

| File | Transcript | Status | Notes |
|------|-----------|--------|-------|
| interview.m4a | interview.m4a.md | Transcribed | 2 speakers identified |
| recording.mp4 | recording.mp4.md | Skipped | Already had transcript |
| bad_file.m4a | — | Failed | Whisper API error: ... |

State the total counts: transcribed, already done, failed.

## Error Handling

- If a Google Drive search returns no results but you expect files, retry once with a broader query before concluding the folder is empty.
- If `download_file_content` returns content that cannot be decoded as audio, log it and skip.
- Never overwrite an existing transcript in Drive — if `<audio_filename>.md` already exists when you reach Step 6e, skip the upload and log it.
- If `/tmp/transcribe_work/` fills up or a write fails, stop and report the disk issue to the user rather than continuing.
