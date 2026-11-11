# CopyPasteBin 1.3-dev — Ubuntu shortcut live test

Date: 2026-11-11
Status: first live series complete; fixes require retesting

## Environment and artifact

The user test ran on a Dell computer with Ubuntu 26.04.1 LTS, GNOME Shell
50.1, Wayland, and Python 3.14.4. It used the user-local installer without
`sudo`, built from commit `987e85a3802a97e2d1fbd0977cbcb867fe233d1f`,
SHA-256 `44d4982b11df8ddeccab0bc5e7d7655a201e181594e529dbb2a00bc82b00e363`.

The account and host names are not recorded because they are unnecessary for
reproducing the test.

## Results

- checksum verification, `--check-only`, user-local installation, and
  extension loading: PASS;
- icon, menu, `Super+Shift+E` configuration, single editor window, autorepeat,
  shortcut cleanup, screen lock, pause, and resume: PASS;
- presenting an existing editor: FAIL — GTK requested presentation, but
  Mutter kept the window in the background and displayed an attention request;
- email followed by a sentence-final period: FAIL; comma, semicolon, and colon:
  PASS;
- a real shortcut conflict, every history scenario, and full image-redaction
  coverage remain incomplete.

Global `org.gnome.shell disable-user-extensions=true` blocked all user
extensions despite the UUID being present in the enabled list. This was not a
CopyPasteBin activation failure.

## Diagnosis and fixes

1. `f637b6c` fixes the email match boundary. The failure occurred in the
   detector itself, before bridge validation, history, deduplication, or the
   banner. A final period remains outside the detection, while a domain
   continuation after a period is still rejected. The ruleset version changes
   from 10 to 11.
2. `b84db7a` retains the local GTK signal but asks GNOME Shell to activate only
   the window with the editor's exact GTK application ID, in direct response
   to a user action. Actual focus is checked after a short delay. The success
   banner remains, while failure gets a separate truthful message.
3. `b8fa43d` adds a read-only warning for
   `disable-user-extensions=true`. The installer never changes the global
   setting.

The email fix is an independent security-backport candidate for the stable
line, but it has not been moved or published.

## Automated verification

After the fixes, the full source command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python3 -m unittest discover -s tests -q
```

completed with `397/397 PASS`. The four image-decoding tests previously
blocked by Glycin/D-Bus passed in this run. No test or isolation control was
weakened.

## Pause and future dictation

The current pause still blocks the clipboard-reading editor and was not
changed. The STT design should distinguish two explicit editor launch modes:

- `clipboard` — reads the clipboard and keeps the current pause gate;
- `blank` — starts with an empty buffer, reads no clipboard content, and may
  remain usable while monitoring is paused.

Dictation in `blank` mode must not resume monitoring automatically or write to
the clipboard. Implementing this split requires a separate decision.

## Live retest scope

The next package should primarily retest sentence-final email detection,
actual editor activation, truthful activation failure reporting, and the
installer warning for the global extension block. Existing features need a
short synthetic-data regression.
