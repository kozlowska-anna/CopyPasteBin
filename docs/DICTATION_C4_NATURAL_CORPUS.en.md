# CopyPasteBin 1.3 — C4 natural Polish corpus plan

Status: **source-approval plan; no new audio has been downloaded**. Reviewed
2026-11-12. The Tatoeba corpus and all earlier results remain unchanged.

## Source decision

The primary proposal is a 15-clip subset of Polish VoxPopuli test data pinned
to revision `5ab868a7cddb87d84224ebfc8112ebd0905fc5bd`. VoxPopuli explicitly licenses
its data as CC0 (separately from its CC BY-NC code/models), attributes the raw
recordings to the European Parliament, and provides Polish transcripts and
pseudonymous `speaker_id` values. Polish data covers 111 hours and 282 speakers.
The full Hub export is about 20.6 GB, so it must not be downloaded. The
Hugging Face Dataset Viewer `/rows` endpoint can expose individual rows and
temporary per-row audio assets.

Mozilla Common Voice 27.0 Polish is CC0 but is a 4.49 GB official archive and
mostly short scripted speech; it is deferred. Its no-reidentification and
no-rehosting conditions would also be retained. FLEURS `pl_pl` is CC BY 4.0
and supports selective rows, but its public schema lacks a speaker identifier
and its domain is read speech; it is a reserve source and cannot count toward
the speaker minimum.

Primary references:

- <https://github.com/facebookresearch/voxpopuli>
- <https://huggingface.co/datasets/facebook/voxpopuli>
- <https://huggingface.co/docs/dataset-viewer/rows>
- <https://mozilladatacollective.com/datasets/cmu5wsxwp00e0nq07m8v0274j>
- <https://commonvoice.mozilla.org/dav/terms>
- <https://huggingface.co/datasets/google/fleurs>

## Closed selection plan

The target is five pseudonymous speakers with three clips each. Every clip
must be 10–30 seconds, total duration 3–6 minutes, with a hard 25 MB transfer
cap. Metadata must have `is_gold_transcript`, `raw_text`, and `speaker_id`.
Selection uses lexical speaker ID order and the lowest stable qualifying
`audio_id`; no real-world identity lookup is permitted. Source and derived WAV
SHA-256 values are recorded, and references are copied only from pinned source
metadata. Hitting the cap or losing selective access stops the task rather
than triggering a full archive download.

VoxPopuli should cover longer natural speech, numbers/dates, names, pace/pause
variation, and punctuation. Everyday conversation, computing vocabulary, and
self-corrections are explicit expected gaps in its parliamentary domain.

The unfilled plan is stored separately in
`audio-manifest.natural-pl.plan.json` and `cases.natural-pl.plan.json`; neither
is executable benchmark input. The future version-3 manifest will be checked
by `validate_natural_audio_manifest.py` for 12–20 exact case/file pairs,
at least three speakers, pinned revisions and licenses, hashes, mono PCM WAV
16 kHz, duration, categories, and explicit coverage gaps.

## Quality methodology v2

Historical `wer`, `cer`, and sequence-only punctuation accuracy remain for
comparability. Report version 4 adds NFC/casefold lexical WER and CER without
punctuation, punctuation-aware CER, and boundary-based counts of correct,
missing, extra, and misplaced marks. Punctuation precision/recall/F1 is only
computed when normalized lexical tokens match; observations blocked by word
errors are reported separately. This prevents a comma moved to another word
boundary from being counted as correct and prevents lexical errors from being
silently treated as punctuation placement failures.

A read-only reanalysis of the preserved Tatoeba result demonstrates the
effect. Vosk lexical CER is 6.383% versus 10.9312% with punctuation; none of
its 11 lexically exact clips has complete punctuation. Whisper is 16.383%
versus 16.3968%; only 6 of 20 clips have words exact enough for independent
placement scoring, and all six have exact punctuation. The historical 80%
Whisper figure was mark-sequence agreement in 16/20 clips, including clips
whose word errors make placement ambiguous. It must not be read as a standalone
0%-versus-80% punctuation benchmark.

After separate corpus approval, both engines will receive identical files:
Vosk `streaming/fast`, Whisper tiny `batch/fast` with Polish selected, three
performance repetitions, and a separate Vosk `realtime` run on longer clips.
Quality conclusions use unique utterances, not repeated executions.

No audio, dependency, model, microphone, or inference was used in this stage.
Separate approval is required for the first bounded audio download, conversion,
and every later benchmark run. Audio stays in the private C4 directory and is
never committed.
