<h1>
  CopyPasteBin
  <img align="right" width="180" alt="CopyPasteBin logo" src="docs/screenshots/ikona.png" />
  <br clear="right" />
</h1>

**English** | [Polski](README.pl.md)

## More control before you paste

CopyPasteBin helps you avoid accidentally sharing sensitive information copied to your clipboard.
It recognizes potentially sensitive data, such as passwords, API keys, payment card numbers, and email addresses, and warns you when something deserves a second look.
You can review the text, anonymize sensitive details, or leave it unchanged. CopyPasteBin helps you make informed decisions without taking control away from you.
Everything runs locally on your computer. Your clipboard content is never sent to the cloud by CopyPasteBin.

CopyPasteBin is an advisory tool. A missing warning means only that none of the
enabled patterns matched; it is not a guarantee that the text is safe.

## Features

- **Sensitive-data detection:** supported patterns include API keys, access
  tokens, recovery keys, payment information, personal identifiers, network
  addresses, private paths, database connection strings, and more.
- **Four risk levels:** low, medium, high, and critical.
- **Review and redaction:** inspect detected content and explicitly replace the
  clipboard only after reviewing the result.
- **Safe Paste:** press `Super+Shift+V` to inspect clipboard text without
  automatically pasting it into the active application.
- **Exact exclusions:** suppress a known low- or medium-risk match without
  disabling its entire category. High- and critical-risk matches cannot be
  permanently excluded.
- **Local history model:** persistent history contains limited metadata and an
  HMAC, not clipboard text. Up to 15 recent text entries can be retained in
  session memory.
- **Configurable protection:** enable or disable detection categories, add
  literal custom rules, pause monitoring, or opt in to clearing an unchanged
  warning-triggering clipboard entry after 1, 5, or 15 minutes.
- **English and Polish interface.**

CopyPasteBin does not take over `Ctrl+V`, globally intercept keyboard input, or
paste text on your behalf.

## CopyPasteBin screenshots

### GNOME Desktop Integration

The panel menu shows whether monitoring is active and opens the session-only
recent clipboard, detection filters, custom rules and exact exclusions,
automatic clearing, language settings, the clipboard editor, pause controls,
and the local About window.

<img width="359" height="608" alt="CopyPasteBin menu in the GNOME panel" src="docs/screenshots/01-gnome-panel.png" />

### Sensitive Data Warning

When an enabled pattern matches, CopyPasteBin displays a risk-colored banner
with safe category names and counts, never the clipboard text itself. The
single action opens the editor for review.

<img width="704" height="159" alt="High-risk CopyPasteBin banner for a detected payment card" src="docs/screenshots/02-high-risk-warning.png" />

### Clipboard Editor & Risk Highlighting

The editor highlights ranges found by the same local detector and prepares a
redaction suggestion. The clipboard changes only after **Replace clipboard**;
canceling leaves it unchanged. The screenshot uses synthetic demonstration
text.

<img width="1079" height="608" alt="Clipboard editor highlighting a synthetic email address and password" src="docs/screenshots/03-clipboard-editor.png" />

### Selective Anonymization

Clicking a highlighted low- or medium-risk match selects its exact range. You
can anonymize only that selection or, after confirmation, add an exact,
case-sensitive exclusion for that value and category. High- and critical-risk
matches can be anonymized but cannot be excluded.

<img width="1079" height="608" alt="Context menu for anonymizing or excluding a selected synthetic email address" src="docs/screenshots/04-selective-anonymization.png" />

### Custom Rules & Exceptions

Custom rules are bounded, local, exact, case-sensitive literals with an
assigned risk level. Each rule can be enabled or disabled. Exact exclusions
are available only for supported low- and medium-risk detections; real
passwords, keys, and other secrets should never be saved as rules or
exclusions.

<img width="1202" height="647" alt="CopyPasteBin editor for synthetic custom rules and exact exclusions" src="docs/screenshots/05-custom-rules-and-exceptions.png" />

### Recent clipboard in session memory

The separate window shows up to 15 recently copied text entries held only in
process memory. Locking the screen, logging out, or stopping the extension
clears the list. Restoring an entry requires an explicit action. This list is
separate from the persistent history, which stores limited metadata and an
HMAC but no clipboard text.

<img width="1039" height="718" alt="Session-only list of synthetic recent clipboard entries" src="docs/screenshots/06-clipboard-history.png" />


## Compatibility

Version 1.0.0 supports the following environment:

| Component | Requirement |
| --- | --- |
| Operating system | Linux |
| Desktop | GNOME Shell 50 |
| Display server | Wayland |
| Python | 3.11 or newer, with `venv` |
| Additional components | GJS, GTK 4, GioUnix, GNOME Extensions, `sha256sum` |

Cinnamon, KDE Plasma, and Xfce desktop integrations are not supported in
version 1.0.0. The installer stops safely when GNOME Shell is unavailable.

## Install version 1.0.0

Download `CopyPasteBin-offline-linux-1.0.0.tar.gz` and a checksum file from
the [v1.0.0 release](https://github.com/kozlowska-anna/CopyPasteBin/releases/tag/v1.0.0).

Verify the archive before extracting it.

Run the read-only compatibility check:

```sh
./install.sh --check-only
```

If the check reports `Kontrola zgodności: OK`, install CopyPasteBin for the
current user:

```sh
./install.sh
```

Installation does not require `sudo`, a package manager, or network access.
Log out and log back in to activate the GNOME Shell extension. CopyPasteBin
should then start automatically.

If it does not appear after the first login, run the included read-only
diagnostic before starting CopyPasteBin manually:

```sh
./diagnose-first-activation.sh
```

To update, run `./install.sh` from the new package. To remove the installed
code, run `./uninstall.sh`. Updates and removal preserve the user's private
configuration and history.

See the [complete offline installation guide (Polish)](docs/offline-installation.md)
for requirements, verification, update, removal, and troubleshooting details.

## Privacy and security

CopyPasteBin is designed to minimize unnecessary access and storage:

- clipboard inspection and pattern matching run locally;
- clipboard text is not uploaded by CopyPasteBin;
- persistent history stores metadata and an HMAC, not original or redacted
  clipboard text;
- recent clipboard entries exist only in process memory and are cleared when
  the extension is disabled, the screen is locked, or the session ends;
- text passed between components uses bounded standard input and output, not
  command-line arguments, environment variables, logs, or temporary files;
- normal detection does not modify the clipboard;
- clipboard replacement requires an explicit action in the editor, except for
  optional automatic clearing that the user must enable first.

CopyPasteBin does not protect against an administrator, another process running
as the same user, a clipboard manager, screen observation, or a compromised
source or destination application. Runtime memory is not guaranteed to be
cryptographically erased and may be affected by swap or hibernation.

Read the [security model (Polish)](SECURITY.md) and the
[version 1 contract (Polish)](docs/v1-contract.md) before relying on
CopyPasteBin in a sensitive workflow.

## Documentation

- [Polish README](README.pl.md)
- [Promotional brochure in English](docs/CopyPasteBin_brochure_EN.pdf)
- [Promotional brochure in Polish](docs/CopyPasteBin_brochure_PL.pdf)
- [Offline installation (Polish)](docs/offline-installation.md)
- [Security model (Polish)](SECURITY.md)
- [Architecture (Polish)](docs/architecture.md)
- [GNOME event backend (Polish)](docs/gnome-event-backend.md)
- [Third-party data (Polish)](docs/third-party-data.md)
- [Changelog (Polish)](CHANGELOG.md)

## Development and verification

The automated suite uses synthetic fixtures and temporary directories. It does
not require real clipboard contents or private user data.

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 benchmarks/detection_quality.py
```

The published 1.0.0 snapshot passed 307 automated tests and the 26-case
detection benchmark. These checks do not replace a live GNOME Shell test.

## License and authorship

Copyright © 2026 Anna Kozłowska.

CopyPasteBin is licensed under
[GNU GPL-3.0-or-later](LICENSE). Third-party notices are provided in
[NOTICE](NOTICE).

Development was assisted by ChatGPT and Codex from OpenAI. CopyPasteBin is an
independent project and is not affiliated with, endorsed by, or sponsored by
OpenAI.
