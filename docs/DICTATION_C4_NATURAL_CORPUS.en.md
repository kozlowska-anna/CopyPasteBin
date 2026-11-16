# CopyPasteBin 1.3 — C4 natural Polish corpus plan

Status: **ParlaSpeech rejected as the primary WER/CER reference; 15 WAV files
retained as candidates for a separate acoustic-challenge benchmark**.
Decision after manual listening: 2026-11-16. The Tatoeba corpus and all earlier
results remain unchanged.

The current decision, alternative-source comparison, and two-suite plan are in
`DICTATION_C4_CORPUS_STRATEGY.en.md`. The sections below preserve the historical
selection, download, and structural-validation evidence; they no longer approve
ParlaSpeech for the primary quality benchmark.

## Historical source decision

The originally selected source was ParlaSpeech-PL 1.0, pinned to Hugging Face
revision `88887ee82cdb7e3f20e7b29d4c1740d0bc630f41`. Its authoritative CLARIN.SI
record licenses audio and transcripts under CC BY-SA 4.0 and attributes Danijel
Korzinek, Nikola Ljubesic, the Jozef Stefan Institute/CLARIN.SI, ParlaMint 4.0
transcripts, and Polish Parliament recordings. The full Hub dataset is about
60.8 GB and must not be downloaded.

Bounded Dataset Viewer pages exposed individual FLAC records whose cached URLs
contain the exact pinned revision. Scanning 420 metadata rows yielded five
qualifying speakers with at least three 10–20 second clips. Names were used only
for temporary grouping; the plan retains `speaker-01` through `speaker-05`.
The deterministic selection contains 15 unique records totaling 195.74 seconds.
All 15 references are non-empty and contain punctuation.

The originally selected row 97 became unavailable and, after explicit approval,
was replaced by row 99 from the same speaker. HEAD returned HTTP 200 without
redirects for every final URL. Exactly 15 FLAC files totaling 3,871,015 bytes
were downloaded into a private mode-0700 directory. Every file and the local
SHA-256 manifest is mode 0600; sizes, FLAC media type, and hashes were verified
again locally. No decoder, playback, conversion, or inference was run. The
transcripts are official and manual, but sentence-to-audio alignment is
automatic and must be reviewed before producing the final manifest.

FLAC files were decoded inside networkless `bwrap` and converted with
GStreamer to mono 16-bit PCM WAV at 16 kHz. The 15 WAV files total 6,264,344
bytes and 195,740.125 ms. A private version-3 manifest passed structural
validation for count, five speakers, format, permissions, hashes, duration,
categories, and explicit coverage gaps. One raw reference (`natural-pl-14`)
contained a parliamentary comment; official `text_normalised` was therefore
used consistently for all cases and retained punctuation. The manifest remains
provisional until a human reviews all audio-reference pairs and category labels.

## Historical VoxPopuli blocker

The pinned revision exists. Current revision `42f01879…` has a Polish tree
identical to the pinned revision; the test Parquet object is
`7139cfca3efa5f25d3f69b8b99d4144d84134a78` and 946,977,412 bytes in both.
Provenance is therefore linked reliably. Selective access nevertheless fails:
`/rows` returns HTTP 500 for both 100 and one row, and `/first-rows` returns
501. The service reports a required 519,677,114-byte scan over its 300,000,000
byte limit. No row metadata or audio was obtained.

Mozilla Common Voice 27.0 Polish is CC0 but is a 4.49 GB official archive and
mostly short scripted speech; it is deferred. Its no-reidentification and
no-rehosting conditions would also be retained. FLEURS `pl_pl` is CC BY 4.0
and supports selective rows, but its public schema lacks a speaker identifier
and its domain is read speech; it is a reserve source and cannot count toward
the speaker minimum.

Primary references:

- <https://hdl.handle.net/11356/1686>
- <https://huggingface.co/datasets/classla/ParlaSpeech-PL>
- <https://clarinsi.github.io/parlaspeech/>

Other references:

- <https://github.com/facebookresearch/voxpopuli>
- <https://huggingface.co/datasets/facebook/voxpopuli>
- <https://huggingface.co/docs/dataset-viewer/rows>
- <https://mozilladatacollective.com/datasets/cmu5wsxwp00e0nq07m8v0274j>
- <https://commonvoice.mozilla.org/dav/terms>
- <https://huggingface.co/datasets/google/fleurs>

## Closed selection plan

The target is five pseudonymous speakers with three clips each. Every clip
must be 10–20 seconds, total duration 3–5 minutes, with a hard 25 MB transfer
cap. Candidates require non-empty `text` and `text_normalised`, FLAC metadata,
a speaker label, and a 10–20 second duration. Qualifying speakers are ordered
by their first row index and the first three rows are selected. No real-world
identity lookup is permitted and names are not persisted. Source and derived WAV
SHA-256 values are recorded, and references are copied only from pinned source
metadata. Hitting the cap or losing selective access stops the task rather
than triggering a full archive download.

ParlaSpeech should cover longer natural speech, numbers/dates, names, pace/pause
variation, and punctuation. Everyday conversation, computing vocabulary, and
self-corrections are explicit expected gaps in its parliamentary domain.

The selected, no-audio plan is stored separately in
`audio-manifest.natural-pl.plan.json` and `cases.natural-pl.plan.json`; neither
is executable benchmark input. The future version-3 manifest will be checked
by `validate_natural_audio_manifest.py` for 15 exact case/file pairs,
exactly five speaker slots, pinned revisions and licenses, hashes, mono PCM WAV
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

No new dependency, model, microphone, audio device, or inference was used.
Download, source hashing, isolated decoding, conversion, and structural
validation are complete. Human audio-reference and category review remains
before finalization. Every later benchmark run still requires separate approval.
