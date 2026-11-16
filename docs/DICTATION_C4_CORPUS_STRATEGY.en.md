# CopyPasteBin 1.3 — C4 Polish STT corpus organization

Status: **project decision and pilot plan; no new audio download**.
Reviewed 2026-11-16.

## Closing the ParlaSpeech assessment

The preserved 15 ParlaSpeech recordings are structurally valid: provenance,
sizes, formats, and SHA-256 values were checked, and conversion ran locally
without network access. This does not make them valid WER/CER references.

Manual listening found differences between spoken words and the official text.
Every reference in a separate five-clip replacement group contained omissions,
additions, or editorial wording changes. Large-room reverberation, amplification,
applause, and prolonged sounds were also reported. These observations do not
prove that every ParlaSpeech clip is unusable, but they are sufficient to reject
the source as the primary verbatim-transcription benchmark.

Decision:

- ParlaSpeech is not the primary natural-dictation corpus;
- existing files, hashes, and manifests remain in place and are not overwritten;
- the 15 recordings are retained as `acoustic-challenge-candidate`;
- current texts are `source-original-unverified` and cannot support credible
  WER/CER;
- `reverberant`, `applause`, `noisy`, and `reference_mismatch` are assigned
  only to clips where they were actually observed;
- any later correction preserves the source text beside a separately reviewed
  human reference.

## Candidates for the primary corpus

| Source | License and access | Strengths | Limitations | Assessment |
| --- | --- | --- | --- | --- |
| PWr-AZON supervised subset | CC BY-SA 4.0; public selective rows through a Hugging Face repack, with the original record linked | Multiple speakers, microphone read speech, supervised paths expose a speaker grouping, and a few rows can be fetched without the full corpus | The repack is not the original publisher; provenance and speaker grouping need cross-checking; some text is highly technical and verbatim accuracy is not yet listening-verified | **Best small-pilot candidate** |
| Common Voice Scripted Speech 27.0 PL | CC0 through Mozilla Data Collective; no re-identification or re-hosting | 139,352 validated clips and 3,477 speakers; user microphones and broad device diversity | The official archive is 4.49 GB, mean clip length is 4.573 s, speech is scripted, and a small reproducible official subset is not currently available without broader access | Best broad candidate, not the first least-privilege pilot |
| CLARIN-PL Mobile Corpus | CC BY 3.0; one 1.44 GB archive | Many speakers, 13 hours of read speech, ordinary phone devices | Telephony differs from a computer microphone; no small official package; references still require listening review | Reserve after selective access is solved |
| CLARIN-PL Studio Corpus | CC BY 3.0; roughly 4.9 GB in several files | Many speakers and controlled recordings | Studio audio is cleaner than typical dictation and requires a large transfer | Control corpus, not primary |
| FLEURS `pl_pl` | CC BY 4.0; public row-level selective audio | Easy small technical pilot and ASR-oriented read speech | Public schema has no speaker identifier; only a few Polish speakers and translated read prompts | Technical fallback |
| BIGOS V2 | CC BY-SA 4.0 wrapper plus source-specific terms; gated Hugging Face access | Unifies 12 Polish sources and many domains in an evaluation format | 27.8 GB, gated access, and the card says the current release retains original references while manually transcribed subsets were planned | Catalog and methodology reference, not immediate source |
| PELCRA/Spokes Mix | CC BY or CC BY-NC depending on subset; form/password access | Conversational speech, many speakers, word-level transcripts and event tags | Multi-party conversation is unlike dictation; additional access and mixed licenses | Future conversational or acoustic-challenge candidate |

Sources:

- <https://huggingface.co/datasets/czyzi0/pwr-azon-speech-dataset>
- <https://zasobynauki.pl/zasoby/korpus-nagran-probek-mowy-do-celow-budowy-modeli-akustycznych-dla-automatycznego-rozpoznawania-mowy,53293/>
- <https://mozilladatacollective.com/datasets/cmu5wsxwp00e0nq07m8v0274j>
- <https://commonvoice.mozilla.org/cv/guidelines?tab=scripted-speech>
- <https://clarin-pl.eu/dspace/items/92004353-58c3-49f0-97d9-66edf1cf1095>
- <https://clarin-pl.eu/dspace/items/cd3f6380-97e6-488f-9a91-c228df5c4ac6>
- <https://huggingface.co/datasets/google/fleurs>
- <https://huggingface.co/datasets/amu-cai/pl-asr-bigos-v2>
- <https://github.com/poleval/2024-asr-bigos>
- <https://docs.pelcra.pl/doku.php?id=spoken_offline_corpora>

## Recommended preliminary test

The first choice is only a **pilot of the supervised PWr-AZON subset**, not
approval of the source.

1. Pin the repack revision and confirm provenance and CC BY-SA 4.0 against the
   original PWr/AZON record.
2. Select 12 metadata-only candidates: four pseudonymous `Speakers/<id>`
   groups, three clips each, preferably 6–15 seconds. Never identify speakers.
3. Prefer ordinary single-speaker microphone sentences. Reject music,
   applause, overlap, highly technical enumerations, and ambiguous numbers or
   abbreviations.
4. Before audio, verify host, pinned revision, type, size, and a 10 MB total
   pilot transfer cap.
5. After separate approval, download only those files, record source SHA-256,
   and prepare a local listening page. Do not run STT.
6. Manually review verbatim agreement, one-speaker audio, reverberation, noise,
   music, applause, clipping, and similarity to desktop dictation.
7. Continue only if at least eight clips pass exactly: two from each of four
   speakers. Fewer passes reject the source instead of editing references to
   fit the benchmark.

## Two independent benchmark suites

`natural-dictation-pl-v1` is the primary WER, CER, RTF, and latency suite. It
contains only single-speaker, low-reverberation clips without music or applause
and with `reference-verified` text.

`acoustic-challenge-pl-v1` is separate and measures robustness to room
reverberation, amplification, noise, applause, and variable microphone
distance. ParlaSpeech remains a candidate. An unverified clip may contribute
performance timings but never WER/CER.

Manifests and results remain separate. Proposed organizational fields are:

- `benchmark_suite`: `natural-dictation-pl-v1` or
  `acoustic-challenge-pl-v1`;
- `acoustic_tags`: observed `clean`, `reverberant`, `applause`, or `noisy`;
- `reference.kind`: `source-original` or `human-corrected`;
- `reference.status`: `unverified`, `verified`, or
  `pending-independent-review`;
- `reference.review`: date, reviewer pseudonym, and listening method without
  private data.

Each suite gets independent WER/CER and independent RTF, initialization,
`completed_ms`, CPU, and RSS aggregates. Reports include the number of clips
excluded from quality scoring due to unverified references and may break down
results by confirmed acoustic tag. The two suites are never combined into a
single headline Polish-STT average. Preserved Tatoeba results remain a
historical adapter check.

## Reference reliability

1. `source-original` is preserved exactly as supplied.
2. `human-corrected` is created from listening only, never from a Vosk,
   Whisper, or other evaluated hypothesis.
3. `unverified` has not been confirmed word for word.

A human correction starts as `pending-independent-review`. A second listening
pass without model output is required for `verified`. Original, correction,
rationale, and file identifier stay separate. `unverified` text is never used
in the WER/CER denominator.

## Security assessment

**Benefit:** a small pilot checks verbatim accuracy and acoustics before a
large transfer or native STT execution.

**New access:** public metadata and, only after separate approval, at most 12
listed audio files. No microphone, clipboard, CPB history, token, account, or
system installation is needed.

**Risks:** repack provenance errors, inaccurate references, expiring URLs,
unexpected size, and accidental retention of public speaker labels.

**Controls:** pinned revision, comparison with the original record, closed row
list, 10 MB cap, redirect-free HEAD checks, SHA-256, mode-0700 directory,
mode-0600 files, no names in Git, networkless `bwrap` conversion, listening
before inference, and no cloud STT.

**Least-privilege result:** this stage ends with the report. No new audio,
account, token, dependency, benchmark implementation change, or inference was
used.
