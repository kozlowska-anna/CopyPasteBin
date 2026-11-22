# CopyPasteBin 1.2.2 release tests

[Polski](RELEASE_TESTS_1.2.2.md) | **English**

This document records preparation of candidate 1.2.2 after removal of the
former polling watcher. It does not broaden the declared compatibility range
and does not replace LIVE testing in a physical GNOME session.

## Candidate identity

- verified release code and configuration commit:
  `415e2264dbeb23faf44d4a2b1cf68662675221bf`;
- application version: `1.2.2`;
- Debian package version: `1.2.2-1`;
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

## LIVE test — PENDING

No test has yet been performed in a physical GNOME Wayland session, and no
upgrade from the published 1.2.1 release has been performed. Before
publication, at minimum confirm:

- upgrade from 1.2.1 to one exactly matched 1.2.2 package set;
- extension activation after logging back in;
- menu, pause, resume, history, and editor behavior with synthetic content;
- absence of the former polling process, service, and launcher;
- manual cleanup of any legacy remnants according to the changelog.

## Evidence boundaries

- no push, tag, GitHub Release, or PPA publication was performed;
- the user's stable installation was not changed;
- no real clipboard, history, or private data was read;
- automated PASS is not presented as LIVE PASS;
- a matching SHA-256 confirms file identity but does not by itself prove that
  the file originated from the declared commit.
