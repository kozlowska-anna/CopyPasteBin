# Changelog

All notable CopyPasteBin changes are recorded in this file.

[Polski](CHANGELOG.md) | **English**

## [1.2.1] - 2026-11-08

### Security

- an `@` character no longer disables the history heuristic unless the entire
  text is a valid email address;
- exactly one trailing `LF` or `CRLF` no longer bypasses the history
  heuristic; the original clipboard content is not modified;
- regression tests and a deterministic synthetic corpus for the history policy
  were added without changing detectors, entropy thresholds, or user settings.

### Usability

- disabling history saving while the list is non-empty now requires
  confirmation in a dialog that states how many entries will be removed;
  canceling preserves the setting and entries, while an empty list causes no
  redundant prompt.

### Boundaries

- this is a corrective release with no new permissions and no configuration
  migration;
- the heuristic retains documented limitations and does not guarantee
  detection of every secret.

## [1.2] - 2026-11-01

### Changed

- recognized secrets and high- or critical-risk detections do not enter the
  in-memory text history, regardless of warning-filter settings;
- a separate history heuristic omits standalone high-entropy strings without
  displaying an additional warning;
- history saving can be disabled independently from the GNOME menu; disabling
  it immediately clears the list and closes its window, but does not stop
  analysis, banners, or the editor;
- the history setting stores only the document version and a boolean value,
  with no content, hashes, or entry identifiers;
- the backend response includes a closed `history_eligible` decision, so a
  matching backend and extension use protocol 2;
- the GNOME menu separates the compact history section with dividers and shows
  text status plus a restrained color accent;
- slightly larger status dots are aligned in one column on the left; the
  history dot is beside the “Clipboard history” row above the unambiguous
  “Enable/Disable history saving” action;
- the history status row remains keyboard- and pointer-accessible after the
  layout change and opens the saved-entry window;
- the About window opens the Polish or English product page according to the
  selected interface language;
- manual update checking opens the appropriate language version of the
  download section; the application still makes no automatic network request;
- the author's personal note remains a source comment and is not shown in the
  application interface;
- the quit action opens a conventional confirmation dialog with **Cancel** as
  the safe default instead of requiring the menu to be opened again;
- post-release development packages use a separate `1.3-dev` channel and do
  not overwrite or change the 1.1 release artifacts.

## [1.1] - 2026-10-26

### Added

- an on-demand GTK 4 editor for permanently covering rectangular regions in
  local PNG and JPEG files;
- saving only to a new metadata-free PNG, with one-step mask undo;
- input-size and image-dimension limits plus tests using synthetic PNG and
  JPEG files;
- a native Debian package `1.1-1` alongside the user-local tar.gz archive.

### Boundaries

- the image editor does not capture the screen, monitor clipboard images, use
  the network, or overwrite existing files;
- file selection uses the system GTK dialog, so the desktop environment may
  create its own thumbnails or recent-file entries;
- the release does not claim cryptographic erasure of images from RAM.

### Packaging and compatibility

- DEB and tar.gz are built from the same source set and contain the same
  backend, GNOME extension, editors, icons, and defaults;
- the DEB has no maintainer scripts, does not start the application, and does
  not enable the extension during administrator-authorized installation;
- the shared backend resolver prefers `/usr/bin/cpb`, then the controlled
  user installation, and does not search `PATH`;
- updates and removal preserve `~/.config/copypastebin` and
  `~/.local/state/copypastebin`;
- automatic warnings, risk levels, and colored banners remain part of the
  shared extension code; the image editor is a separate process and does not
  use the clipboard or text-detection engine.

## [1.0.0] - 2026-10-18

First public Linux release.

### Added

- local sensitive-text detection and redaction with `low`, `medium`, `high`,
  and `critical` risk levels;
- event-driven GNOME Shell 50 integration on Wayland, without a polling
  clipboard watcher;
- the `Super+Shift+V` Safe Paste shortcut, which analyzes text on demand and
  never pastes automatically;
- an editor with explicit selection redaction and exact exclusions limited to
  low- and medium-risk categories;
- local rules, filters, pause, and optional delayed clearing of warning
  clipboard content;
- content-free metadata history and a session list of up to 15 recent texts
  held only in RAM;
- Polish and English interfaces, an About window, and desktop visual
  integration;
- local installer, updater, uninstaller, and bounded first-activation
  diagnostics operating without `sudo` or network access.

### Security and privacy

- content travels between components through bounded `stdin`/`stdout`, not
  process arguments, environment variables, or temporary files;
- persistent history stores metadata and an HMAC, but neither original nor
  redacted text;
- screen lock, pause, and extension disable stop reads and clear the session
  text list;
- the installer preserves unrelated GNOME extensions, rejects symbolic links
  at targets, and rolls back a failed update;
- the most heuristic filters—`TOKEN`, `HOME_PATH`, and
  `POSSIBLE_SEED_PHRASE`—are disabled by default, while service-specific
  secret filters remain active;
- `high` and `critical` categories cannot receive a persistent exclusion.

### Distribution

- the offline package installs for one user and preserves settings and history
  across update and removal;
- the release archive has normalized owner/group `0/0`, fixed timestamps,
  mode `0555` for directories and scripts, and `0444` for other files;
- wheel input is copied to a temporary tree with fixed permissions, making the
  result independent of local checkout permissions and `umask`;
- an external SHA-256 checksum allows artifact-integrity verification.

### Compatibility

- the confirmed release scope is GNOME Shell 50 on Wayland with Python 3.11
  or newer;
- Linux Mint Cinnamon, KDE Plasma, and Xfce have no desktop integration in
  version 1.0; the installer stops safely when GNOME Shell is absent;
- other desktop environments, OCR, and Windows remain outside this release.

### Limitations

- no warning is not a guarantee of safety or complete detection;
- the application does not protect against a system administrator, another
  process running as the same user, a clipboard manager, screen observation,
  or a compromised destination application.
