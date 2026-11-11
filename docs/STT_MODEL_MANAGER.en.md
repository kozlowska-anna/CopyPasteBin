# CopyPasteBin 1.3 — on-demand STT models

Status: approved architecture and validated manifest; downloader and GUI are
not implemented yet.
Date: 2026-11-12

## Product decision

An STT model is optional data, independent from the CPB installation and the
engine version. CPB never downloads models at startup or during an update. A
download starts only after the user clicks **Download** and confirms the
source, license, download size, and required space. Installed models work
offline and can be removed independently. A missing model disables dictation
only, not clipboard protection or history.

## Architecture

```text
dictation settings (GJS / GTK 4, no network)
  -> closed model ID from the bundled catalog
  -> separate downloader (network, no microphone or clipboard)
  -> private partial file + size limit + SHA-256
  -> atomic publication in model storage

editor -> STT worker (read-only model, audio only in an active session,
                      separate network namespace without internet access)
```

The GUI passes only a closed model identifier, never a URL, digest, or path.
The downloader reloads the catalog bundled with CPB. Engine and model versions
are independent and the manifest declares their allowed combinations.

## Manifest and integrity policy

`src/copypastebin/data/stt-models-v1.json` is a closed, versioned allowlist.
Each entry contains localized names, language, model version, compatible
engine versions, HTTPS source, exact size, required space, SHA-256, format,
license, relative installation path, and approximate RAM. Insufficiently
authenticated models use `download.enabled=false` and a public limitation
instead of a digest.

The parser rejects unknown fields, HTTP, credentials in URLs, duplicates,
unknown formats, invalid sizes or hashes, absolute and parent paths,
backslashes, and a symlinked manifest.

Whisper tiny has an immutable source commit, exact size, and published SHA-256.
Vosk `small-pl-0.22` is listed as compatible with Vosk 0.3.45, but **Download**
stays disabled. Upstream publishes no independently verifiable digest; the C4
first-download hash supports repeatability but not authenticity. Enabling it
requires a trustworthy upstream digest, signed provider manifest, or a
separately approved distribution channel.

## Storage and lifecycle

```text
${XDG_DATA_HOME:-$HOME/.local/share}/copypastebin/models/
  .incoming/<random-token>/
  <engine>/<engine-version>/<model>/
```

Directories use `0700` and files `0600`. The future downloader creates an
exclusive no-follow partial file on the destination filesystem, reserves
space, imposes its own byte limit, requires HTTPS on every allowlisted
redirect, verifies exact size and SHA-256, synchronizes data, and atomically
renames it. Archive support must reject absolute/parent paths, backslashes,
devices, links, and expansion beyond a fixed limit.

A working model remains until its replacement is fully verified. Cancellation
or crash cleanup affects only that operation's partial object, starts no
network access, and rejects links or invalid ownership/modes. Removal requires
confirmation, derives the target from a manifest ID, does not follow links,
and is refused while an active session holds the model.

## GTK 4 integration

The **Language models** section shows name, language, download and disk sizes,
RAM, license, source, and compatible engine. Closed states are:

- `not-installed` — **Download**;
- `downloading` — progress and **Cancel download**;
- `ready` — **Select** and **Remove**;
- `error` — content-free public error and retry;
- `unavailable` — no download action and a visible integrity limitation.

Every download has a confirmation dialog. Closing the window cannot turn it
into a hidden background operation: the user confirms cancellation or the UI
remains visible. **Ready** appears only after verification and atomic
publication; **Select** requires a compatible engine. There are no automatic
model updates. With no model, the microphone control links to this section and
does not affect clipboard protection.

## Permissions and isolation

| Component | Receives | Does not receive |
| --- | --- | --- |
| catalog/GUI | public catalog and status | network, microphone, clipboard, model writes |
| downloader | network after confirmation; `.incoming` and model writes | microphone, audio, history, clipboard, `sudo` |
| STT worker | read-only model, active audio stream, bounded pipe | network, model writes, history, clipboard |

The STT worker uses `bwrap --unshare-net` without a broad `/` bind. It receives
only libraries, one engine/model, bounded IPC, required `/proc`, and an empty
`/tmp`. Production adds only the selected audio input during an explicit
session. An `offline=true` field is not evidence of isolation.

The downloader is a separate network process without audio devices or CPB
configuration, history, and clipboard access. HTTPS plus SHA-256 protects the
artifact; a host allowlist and redirect limit constrain the client. The exact
CDN redirect policy needs approval before network code is implemented.

## Main risks

| Risk | Safeguard |
| --- | --- |
| replaced or truncated model | pinned URL, exact size, SHA-256 |
| zip bomb / path traversal | limits and per-entry validation |
| write outside storage | manifest ID, `O_NOFOLLOW`, validated relative path |
| crash or low disk space | reservation, private partial, atomic publication |
| network during STT | separate inference network namespace |
| active model removal | session lock and confirmation |
| false Vosk authenticity | download disabled pending independent evidence |
| engine/model mismatch | compatibility matrix checked on select and start |

## 1.3 scope and implementation status

The manifest, parser, and tests can land without delaying the benchmark. They
add no network, dependency, or stable-product behavior. The order remains:

1. finish the `whisper-cli` adapter, approved corpus, and Vosk/Whisper benchmark;
2. select the supported engine/model from measurements;
3. add a small UI and single-file downloader for selected entries;
4. test cancellation, disk exhaustion, crashes, redirects, and atomic publication;
5. add archives or Vosk only after resolving integrity.

Implemented: schema v1, independent model/engine versions, compatibility,
no-network parsing, local size/SHA-256 verification, link rejection, and tests
with a fake model. Not implemented: HTTP, GUI, progress, cancellation,
installation, removal, extraction, or updates. The new mechanism downloaded no
real model.
