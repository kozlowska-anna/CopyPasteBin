# CopyPasteBin 1.2.1 release tests

[Polski](RELEASE_TESTS_1.2.1.md) | **English**

This document records the scope and results of testing candidate 1.2.1. It
does not broaden the declared compatibility range and does not replace a code
audit.

## Candidate identity

- declared commit: `f56cf8af56a00902fcc81f2338967851c7213661`;
- Fedora Live archive: `CopyPasteBin-linux-1.2.1-test2.tar.gz`;
- archive SHA-256:
  `ecb60fd3db21170ead48689a9ac3bef480713185cc925bc38dd0105558ab5abc`;
- application version: `1.2.1`;
- GNOME extension version: `8`.

## Fedora Live — PASS

The test was performed on 8 November 2026 using Fedora 44 Workstation Live,
GNOME 50.0, Wayland, and Python 3.14.3. A user-local tar.gz installation was
used without `sudo`. The extension was active.

The following were confirmed:

- ordinary text enters the in-memory history;
- a valid email address retains its expected warning and may enter history;
- a suspicious string containing `@` does not bypass the history heuristic;
- exactly one trailing `LF` or `CRLF` does not bypass the history heuristic;
- disabling non-empty history shows a warning with the correct entry count;
- **Cancel** is the safe default and Enter preserves history;
- confirmation disables saving and removes the entries;
- disabling empty history shows no redundant warning;
- installation, automatic start after login, pause, resume, the text editor,
  and responsiveness passed smoke tests.

The `LF` and `CRLF` cases were repeated after observing that copying the
complete `printf` command itself creates an additional clipboard event. Both
cases passed after clearing history and repeating the procedure in a
controlled way.

## Test PPA — PASS within the tested scope

On a physical Ubuntu Resolute system, packages were upgraded from
`1.2.1-1~test1` to `1.2.1-1~test2` without prior removal. APT downloaded and
configured exactly matching versions of:

- `copypastebin`;
- `copypastebin-backend`;
- `gnome-shell-extension-copypastebin`.

After logging back in, the system extension at
`/usr/share/gnome-shell/extensions/copypastebin@kozlowska-anna.github.io`
reported version `8`, was enabled, and had state `ACTIVE`. A synthetic
history entry and the complete warning flow were confirmed: canceling with
Enter, preserving the entry, explicitly disabling with removal, and no warning
for an empty history.

## Stable PPA — PASS

On a physical Ubuntu Resolute system, a controlled transition was performed
from `1.2.1-1~test2` to the stable PPA. Before installation, APT reported the
same `1.2.1-1` candidate for all three packages. One operation installed the
exactly pinned versions:

- `copypastebin 1.2.1-1`;
- `copypastebin-backend 1.2.1-1`;
- `gnome-shell-extension-copypastebin 1.2.1-1`.

No user-local backend or extension left by a tar.gz installation was present.
The active extension came exclusively from the system path
`/usr/share/gnome-shell/extensions/copypastebin@kozlowska-anna.github.io`,
reported version `8`, and had state `ACTIVE`.

The final smoke test after logging back in passed: ordinary text entered the
in-memory history; the warning shown before disabling non-empty history stated
the correct number of entries; Enter selected the safe cancel action and
preserved the entries; explicit confirmation disabled saving and cleared the
list; and the About window reported version `1.2.1`.

## Final GitHub archive — PASS

The final `CopyPasteBin-linux-1.2.1.tar.gz` was built from documentation
commit `eb963180f1912bf21704c54444137db4cfcc994b`. Two independent builds were
byte-for-byte identical. Archive SHA-256:

`75ea7300d688402737e27ad07bc679ae6a952679cd6cffe10257a07f99d23a6b`

A comparison of the extracted trees against candidate `test2` found
differences only in `SECURITY.md` and `SECURITY.pl.md`. The application
payload, wheel, extension, installer, and all other files were identical. All
internal `SHA256SUMS` checks passed, and `./install.sh --check-only` reported
`Kontrola zgodności: OK` without making changes.

## Evidence boundaries

- the Fedora Live test did not cover DEB or PPA installation;
- the PPA test covered an upgrade and the changed feature, not every detection
  category;
- the stable-PPA test was a final installation and changed-feature smoke test,
  not a complete rerun of every application capability;
- the complete image-redaction flow and benchmarks were not rerun;
- a matching SHA-256 confirms file identity but does not by itself prove that
  the archive originated from the declared commit.
- the final archive with documentation-only changes was not installed again
  in a LIVE session; its application payload is byte-identical to candidate
  `test2`, which received the Fedora Live PASS.
