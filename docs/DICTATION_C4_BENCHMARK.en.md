# CopyPasteBin 1.3 — C4 real STT benchmark plan

Status: Vosk 0.3.45, Vosk `small-pl-0.22`, whisper.cpp 1.9.5, Whisper tiny,
the `whisper-cli` adapter, and a technical audio corpus are prepared locally.
Updated: 2026-11-12.

Every candidate receives the same mono 16-bit PCM WAV at 16 kHz, three times.
The model is loaded afresh for each run, but OS caches are not flushed, so the
first run is not labelled a guaranteed cold start. Three repetitions of one
clip are not independent quality samples; quality conclusions are based on 20
unique clips. Engine order is rotated between repetitions.
Final-quality metrics are WER, CER, punctuation accuracy, model initialization,
final latency, real-time factor, CPU, peak RSS, and disk size. Endpoint latency
is interpreted only for real-time input. Live metrics are compared only inside
an explicit `streaming` or
`windowed` class. Vosk can emit native partials; `whisper-cli` is initially a
`batch` test and receives no invented first-partial value. Reprocessing a
growing window must be labelled `windowed`, not streaming.

`input_pacing=fast` feeds a file without waiting and measures throughput,
quality, CPU, RAM, and initialization. `input_pacing=realtime` schedules PCM
chunks from a monotonic clock and is the only mode whose partial and endpoint
lags represent simulated live dictation. Reports keep these pacing modes
separate. Whisper CLI remains `batch/fast`.

`run_isolated.py` is the only supported entry point. It establishes the bwrap
profile; before spawning an adapter, `run_adapter.py` verifies read-only input
mounts, absent home/password/audio-device paths, no external interfaces or
default routes, and zero effective capabilities. It then validates the C1–C3
session frames, measures resources, and writes a private `0600` format-3 result
without printing transcripts. Benchmark-only audio-position fields make live
lag measurable without changing the editor's production protocol.
`analyze_runs.py` aggregates metrics without content. `completed_ms` has one
definition for both engines: adapter start through clean process completion
after the final frame; `final_result_ms` is the earlier observation of that
frame. CPU, wall time, and RSS remain separate. Adapter readiness is also
separate from `model_init_ms`: Vosk's initialization covers adapter start
through library/model/recognizer readiness, while Whisper's is the native
CLI-reported model-load time. Those differently scoped values must not be
compared directly. The report labels their scope and includes mean and median
completion time, mean/max RSS, and per-clip repeat spread.
`validate_audio_manifest.py` accepts only checksum-pinned mono PCM files inside
one isolated audio directory.
The launcher compares the complete command against one of two approved
argument lists. It rejects arbitrary Python scripts, extra flags, and model
names that do not match the candidate. Each adapter runs in a separate process
group that is killed as a whole on failure or timeout; Whisper's internal
timeout expires five seconds before the outer runner limit.

The first real technical set is pinned in `cases.tatoeba-pl.json` and
`audio-manifest.tatoeba-pl.json`: 20 short utterances (28.395 seconds total)
from one Tatoeba speaker, `antio`. Audio is CC BY 4.0 and reference text is
CC BY 2.0 FR. The manifest records sentence IDs, source URLs, source MP3 and
derived WAV SHA-256 values, and the GStreamer conversion to mono 16-bit PCM
WAV at 16 kHz. One Tatoeba/Wikimedia source pair was byte-compared. This is
enough for adapter readiness and an initial technical comparison, but its
short duration, single speaker, and limited content are not representative
STT-quality evidence. A later quality corpus should still cover 2–4 minutes,
more speakers, numbers, names, technical terms, pauses, and corrections.
Private user recordings remain excluded.

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
The unsafe broad-root example has been removed. The controlled launcher uses
separate network/PID/IPC/UTS namespaces, drops capabilities, and mounts only
`/usr`, `/lib`, `/lib64`, the loader cache, the specific harness, engine, model,
and read-only audio plus writable results. It exposes no `/home`, `/etc/passwd`,
or `/dev/snd`. `run_adapter.py` refuses direct execution, so a flag or
environment claim alone cannot mark a run offline.

Recommended order: with separate approval test Vosk and Whisper tiny on the
pinned technical corpus, including native Vosk streaming. Add base and then
small only if resource results justify them;
decide about a Whisper `windowed` adapter only after those measurements.
Microphone and editor integration remain outside C4.

The portable `$XDG_DATA_HOME` paths and the safe launcher command are in the
Polish version; both documents describe the same pins, boundaries, and
methodology.
