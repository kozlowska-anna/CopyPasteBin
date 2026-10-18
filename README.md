<h1>
  <img align="right" width="160" alt="CopyPasteBin logo" src="docs/screenshots/ikona.png" />
  <br /><br /><br />
  CopyPasteBin
</h1>

**English** | [Polski](README.pl.md)

[Download / Installation](#install-version-100)

## More control before you paste

CopyPasteBin helps you notice sensitive information in copied text before it
reaches a chat, email, document, or terminal. Analysis runs locally, and the
decision always stays with you.

### Why use it

- **Notice risk earlier.** A warning appears when text resembles a supported
  kind of sensitive information.
- **Keep the decision.** CopyPasteBin helps you review text, but it does not
  paste it or change the clipboard automatically by default.
- **Keep data on your device.** Detection and redaction run without sending
  clipboard contents to cloud services.
- **Prepare safer text.** Safe Paste and the editor help remove or redact
  selected values before you share them.

### In everyday work

Copy as usual. CopyPasteBin works in the background and gives you a moment to
review text before using it in a conversation, message, document, or command.

### You stay in control

CopyPasteBin warns and suggests edits, but saving a replacement requires an
explicit action. Optional clearing of an unchanged warning-triggering clipboard
entry works only after you enable it.

### Honest protection boundaries

No warning means only that no known, enabled pattern matched. CopyPasteBin
helps reduce risk, but it cannot guarantee detection of all sensitive
information and does not block pasting.

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

### [⬇ Download CopyPasteBin 1.0.0 for Linux (.tar.gz)](https://github.com/kozlowska-anna/CopyPasteBin/releases/download/v1.0.0/CopyPasteBin-offline-linux-1.0.0.tar.gz)

Also download the [SHA-256 checksum](https://github.com/kozlowska-anna/CopyPasteBin/releases/download/v1.0.0/CopyPasteBin-offline-linux-1.0.0.tar.gz.sha256),
then follow the [English installation instructions](docs/offline-installation.en.md)
to verify the file before opening it.

Run the read-only compatibility check:

```sh
./install.sh --check-only
```

If the compatibility check succeeds, install CopyPasteBin for the current
user:

```sh
./install.sh
```

Installation does not require `sudo`, a package manager, or network access.
Log out and log back in to activate the GNOME Shell extension. CopyPasteBin
should then start automatically.

To update, run `./install.sh` from the new package. To remove the installed
code, run `./uninstall.sh`. Updates and removal preserve the user's private
configuration and history.

See the [complete English installation guide](docs/offline-installation.en.md)
for requirements, download links, verification, update, removal, and
troubleshooting details.

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

Read the [security model](SECURITY.md) and the
[version 1 contract (Polish)](docs/v1-contract.md) before relying on
CopyPasteBin in a sensitive workflow.

## Documentation

- [Technical overview (Polish)](docs/technical-overview.pl.md)
- [Offline installation (English)](docs/offline-installation.en.md)
- [Instalacja offline (polski)](docs/offline-installation.md)
- [Security model (English)](SECURITY.md)
- [Model bezpieczeństwa (Polish)](docs/security.pl.md)
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
