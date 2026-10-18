**English** | [Polski](README.pl.md) <img width="256" height="256" alt="ikona" src="https://github.com/user-attachments/assets/e88d6ef5-b997-4971-a979-07358f366ae0" />


# CopyPasteBin

## More control before you paste

CopyPasteBin helps you avoid accidentally sharing sensitive information copied to your clipboard.
It recognizes potentially sensitive data, such as passwords, API keys, payment card numbers, and email addresses, and warns you when something deserves a second look.
You can review the text, anonymize sensitive details, or leave it unchanged. CopyPasteBin helps you make informed decisions without taking control away from you.
Everything runs locally on your computer. Your clipboard content is never sent to the cloud by CopyPasteBin.

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

## 📸 CopyPasteBin Screenshots

### GNOME Desktop Integration

CopyPasteBin integrates directly into the GNOME desktop, providing quick access to clipboard history, detection filters, privacy settings, and protection controls from the system panel.

<img width="359" height="608" alt="01-gnome-panel" src="https://github.com/user-attachments/assets/8373d4a6-1f01-45bc-86f9-e1ec5ac6668d" />

### Sensitive Data Warning

CopyPasteBin detects potentially sensitive clipboard content and displays clear, color-coded warnings based on risk severity. Open the editor to review detected information before sharing it.

<img width="704" height="159" alt="02-high-risk-warning" src="https://github.com/user-attachments/assets/8c220e27-07c2-4553-b32d-3040b0d78198" />

### Clipboard Editor & Risk Highlighting

Review detected sensitive information and anonymize
selected content before replacing the clipboard.

<img width="1079" height="608" alt="03-clipboard-editor" src="https://github.com/user-attachments/assets/b6175965-3fec-4eca-a217-724b7df4b5ed" />

### Selective Anonymization

Take control of individual detections with contextual actions. Anonymize selected content or exclude a specific detection without changing the rest of your text.

<img width="1079" height="608" alt="04-selective-anonymization" src="https://github.com/user-attachments/assets/bde143c5-cd0f-4739-a3c9-b24d8f08b776" />

### Custom Rules & Exceptions

Personalize clipboard protection with custom, case-sensitive words and phrases. Assign risk levels, enable or disable individual rules, and configure precise exceptions for supported detection categories.

<img width="1202" height="647" alt="05-custom-rules-and-exceptions" src="https://github.com/user-attachments/assets/e9c8aac8-425c-4894-8c41-529c2bc33f75" />

### Recent Clipboard History

Quickly browse recently copied content from the GNOME panel. CopyPasteBin keeps a temporary clipboard history in memory, making it easier to find and reuse text without relying on cloud storage.

<img width="1039" height="718" alt="06-clipboard-history" src="https://github.com/user-attachments/assets/0500ea09-4055-4aba-a07d-47210744da5d" />


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
the GitHub.

[Download CopyPasteBin 1.0.0](https://github.com/kozlowska-anna/CopyPasteBin/releases/tag/v1.0.0).

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

See the [complete offline installation guide](docs/offline-installation.md) for
requirements, verification, update, removal, and troubleshooting details.

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
[version 1 contract](docs/v1-contract.md) before relying on CopyPasteBin in a
sensitive workflow.

## Documentation

- [Polish README](README.pl.md)
- [Promotional brochure in English](docs/CopyPasteBin_brochure_EN.pdf)
- [Promotional brochure in Polish](docs/CopyPasteBin_brochure_PL.pdf)
- [Offline installation](docs/offline-installation.md)
- [Security model](SECURITY.md)
- [Architecture](docs/architecture.md)
- [GNOME event backend](docs/gnome-event-backend.md)
- [Third-party data](docs/third-party-data.md)
- [Changelog](CHANGELOG.md)

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
