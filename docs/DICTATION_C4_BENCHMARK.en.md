# CopyPasteBin 1.3 — C4 real STT benchmark plan

Status: Vosk 0.3.45, Vosk `small-pl-0.22`, whisper.cpp 1.9.5, and Whisper tiny
are prepared locally; approved audio and a `whisper-cli` adapter are missing.
Updated: 2026-11-12.

Every candidate receives the same mono 16-bit PCM WAV at 16 kHz, three times.
Final-quality metrics are WER, CER, punctuation accuracy, model initialization,
final latency, real-time factor, endpoint latency, CPU, peak RSS, and disk
size. Live metrics are compared only inside an explicit `streaming` or
`windowed` class. Vosk can emit native partials; `whisper-cli` is initially a
`batch` test and receives no invented first-partial value. Reprocessing a
growing window must be labelled `windowed`, not streaming.

`run_adapter.py` validates the C1–C3 session frames, measures resources, and
writes a private `0600` result without printing transcripts. `analyze_runs.py`
aggregates metrics without content. `validate_audio_manifest.py` accepts only
checksum-pinned mono PCM files inside one isolated audio directory.

The current text cases are for adapter mechanics, not STT-quality evidence.
The quality corpus should contain 12–20 Polish clips totalling about 2–4
minutes and covering short/long speech, numbers and dates, names, Polish
characters, punctuation, computer/AI terminology, pauses, corrections, and an
unfinished sentence. Mozilla Common Voice Polish 27.0 is listed as CC0-1.0,
but the full archive is about 4.49 GB. No clip was downloaded; first determine
whether a deterministic small subset can be obtained without the full archive.
Private user recordings are excluded.

## Pinned dependencies

| Item | Pin | Download | Integrity | License |
| --- | --- | ---: | --- | --- |
| local CMake | PyPI 4.4.4 x86_64 wheel | 30,245,729 B | SHA-256 `f773a054…820238` | BSD-3-Clause / Apache-2.0 wrapper |
| libvosk | PyPI wheel 0.3.45; tag commit `cf2560c…` | 7,173,758 B | SHA-256 `25e02509…619f` | Apache-2.0 |
| Polish Vosk model | `small-pl-0.22` | about 50 MB | **no published SHA-256** | Apache-2.0 |
| whisper.cpp | v1.9.5, `d1be6fde11ac6e0407606b4e42fe72d34add8037` | Git | pinned verified tag/commit; no archive SHA | MIT |
| Whisper tiny/base/small | HF commit `5359861c…` | 77,691,713 / 147,951,465 / 487,601,967 B | official LFS SHA-256 values in `artifacts.json` | MIT |

The exact URLs and complete hashes are in `artifacts.json`. The Vosk model
page publishes the approximate size and license but no SHA-256. A hash observed
after the first download can make later local runs repeatable, but is not
independent evidence for the first download.

The current host is x86_64 with 8 logical CPUs and about 16 GB RAM. GCC/G++,
`make`, `bwrap`, and `unshare` are available. Pinned CMake was extracted
locally without modifying system Python. The Vosk wheel was likewise extracted
only for `libvosk.so`; it was not installed. FFmpeg/SoX remain unnecessary
when audio is prepared in the required WAV format.

Native code execution, opaque model files, voice data, and result files are
the new risks. Mitigations are pinned sources, published hashes where
available, source review, size limits, a separate user directory, a network
namespace for inference, read-only inputs, private `0600` results, public
licensed audio only, no microphone, and no clipboard or CPB-history access.
The original `bwrap --unshare-net` example exposed a broad read-only `/` and is
retained only as a historical draft. Verified Vosk and Whisper profiles use
separate network/PID/IPC/UTS namespaces and mount only `/usr`, `/lib`, `/lib64`,
the loader cache, the specific harness, engine, model, and read-only audio plus
writable results. They expose no `/home`, `/etc/passwd`, or `/dev/snd`. The
`--offline` metadata flag alone is not proof of isolation.

Recommended order: add the `whisper-cli` adapter, approve and pin audio, then
with separate approval test Vosk and Whisper tiny final quality and native
Vosk streaming. Add base and then small only if resource results justify them;
decide about a Whisper `windowed` adapter only after those measurements.
Microphone and editor integration remain outside C4.

Exact download, extraction, build, run, report, and recoverable removal
commands are in the Polish version above; both documents describe the same
pins, boundaries, and methodology.
