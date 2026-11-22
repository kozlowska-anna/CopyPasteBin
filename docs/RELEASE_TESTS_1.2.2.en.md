# CopyPasteBin 1.2.2 release tests

[Polski](RELEASE_TESTS_1.2.2.md) | **English**

This document records preparation and testing of candidate 1.2.2 after
removal of the former polling watcher. It does not broaden the declared
compatibility range.

## Candidate identity

- verified release code and configuration commit:
  `415e2264dbeb23faf44d4a2b1cf68662675221bf`;
- application version: `1.2.2`;
- Debian package version: `1.2.2-1`;
- version tested from the PPA: `1.2.2-1~test1`, from upload commit
  `603e3ae2452f5c4f9318062f93cf7ebf8f11df7c`;
- the stable PPA source was built from merged `main` commit
  `7653fa317b72336695ce03f39c35fa74f28f50fb`;
- GNOME extension version: `8` (no extension-code change requiring a new
  metadata version);
- local branch: `codex/cpb-1.2.2-release`.

## Automated tests — PASS

On 22 November 2026, the following were run on Linux:

- 291 product, integration, security, installation, and packaging tests;
- 26 static-site tests;
- 317 of 317 tests passed in total;
- `git diff --check` reported no errors.

Packaging coverage included the offline bundle, three split DEB packages,
installation migration, and a Debian source-package build from the current
commit.

## Artifact reproducibility and identity — PASS

Two independent builds produced byte-for-byte identical files for each
artifact type. SHA-256 of the local candidates:

- `CopyPasteBin-linux-1.2.2.tar.gz`:
  `53a86553690aa9eb3d38c3277bd2fd40eaf688c2bdbf5a72fb47c797ab0f6715`;
- `copypastebin-backend_1.2.2-1_all.deb`:
  `b949e5cebbaeebdafe38712e88fad2e5aaa232ca76bd1481b3f3a2febf692f58`;
- `gnome-shell-extension-copypastebin_1.2.2-1_all.deb`:
  `23ac0d468e776a4e0ede33f2ca73c82b73efcb69106fa7ccbc67d7a372c674ae`;
- `copypastebin_1.2.2-1_all.deb`:
  `abe221d435663eac5fca57d4662fd80b30783a63529f1184899e909cc3051fa2`.

These are local artifacts in a temporary directory, not published GitHub
Release or PPA files.

## Isolated installation test — PASS

The test used only a synthetic home directory and synthetic state:

- `install.sh --check-only` confirmed compatibility without changes;
- user-local installation with `--no-enable` completed successfully;
- the backend reported product version `1.2.2` and protocol version `2`;
- the removed `cpb watch start` command exited with the ordinary argument
  error code `2`;
- uninstall removed the application and extension code;
- synthetic configuration and synthetic state were preserved;
- neither the former `copypastebin-watcher.service` nor the
  `copypastebin-start.desktop` launcher was created.

Inspection of the archive and DEB payloads found no watcher, service, former
launcher, audio file, or model payload.

## LIVE test from the test PPA — PASS

On 22 November 2026, the user performed a controlled upgrade on Ubuntu
Resolute, GNOME Shell 50.1, and Wayland. The test PPA supplied exactly matched
`1.2.2-1~test1` versions of `copypastebin`, `copypastebin-backend`, and
`gnome-shell-extension-copypastebin`. Absence of a user-local tar.gz
installation was confirmed before the upgrade.

After logging back in, the following were confirmed:

- the system extension under `/usr/share/gnome-shell/extensions` reported
  version `8`, was enabled, and had state `ACTIVE`;
- the backend reported product version `1.2.2` and protocol version `2`;
- the former service was inactive and unknown to systemd, and neither its
  unit file nor the former launcher file existed;
- no `wl-paste`, watcher, or `cpb watch` process was running, while
  `cpb watch start` exited with the ordinary argument error code `2`;
- the menu remained open without flicker, focus theft, or spontaneous closing;
- pause and resume worked;
- ordinary synthetic content entered history;
- a synthetic password assignment produced a warning and did not enter
  history, while the previous ordinary entry remained;
- safely canceling the disable-history action preserved history;
- the editor worked with synthetic text, and the About window reported
  version `1.2.2`.

No manual cleanup of legacy remnants was needed because none were present.

## Stable PPA — PASS

On 22 November 2026, the source and all three `1.2.2-1` packages reached
`Published` status in the stable PPA for Ubuntu Resolute. Two independent
source builds were byte-for-byte identical. The locally built binary packages
had the same SHA-256 values as the candidate verified before LIVE testing.

The user performed a controlled transition of all three packages from
`1.2.2-1~test1` to one exactly matched `1.2.2-1` set, then removed the test
PPA. `apt-cache policy` showed the stable PPA as the only source of the
installed and candidate `1.2.2-1` version.

After logging back in, the final smoke test confirmed:

- the system extension under `/usr/share` reported version `8` and state
  `ACTIVE`;
- the backend reported product version `1.2.2` and protocol version `2`;
- no `wl-paste`, watcher, or `cpb watch` process was running;
- the menu remained open without flicker or spontaneous closing;
- pause and resume worked;
- ordinary synthetic text entered history.

## Evidence boundaries

- tag `v1.2.2` points to commit
  `18d10b560716af1a17fadd38bfa2532e5e4a59e3`, and the public GitHub Release
  contains the tar.gz archive, three DEB packages, and `SHA256SUMS`;
- every public GitHub Release asset passed `SHA256SUMS` verification and was
  byte-identical to the local final-release set;
- stable package `1.2.2-1` was published in the stable PPA;
- test package `1.2.2-1~test1` remained confined to the test PPA, which was
  removed from the test computer's configuration after the stable upgrade;
- the test computer was intentionally upgraded from stable `1.2.1-1` to the
  test-PPA candidate and then to stable `1.2.2-1`;
- no real clipboard, history, or private data was read;
- GNOME interaction results are LIVE evidence reported by the user;
- a matching SHA-256 confirms file identity but does not by itself prove that
  the file originated from the declared commit.
