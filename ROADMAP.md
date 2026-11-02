Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
# CopyPasteBin roadmap

**English** | [Polski](ROADMAP.pl.md)

This roadmap shares the direction of CopyPasteBin without turning early ideas
into release promises. It contains no fixed dates. Priorities may change after
testing, user feedback, security review, or changes in supported desktop
platforms.

## Product identity and design principle

CopyPasteBin is a privacy-focused clipboard manager, not a tool for archiving
everything. Development should strengthen three everyday tasks: noticing risk
after content is copied, preparing or redacting that content, and making an
informed decision about what will ultimately be pasted.

The principle is: **keep as little as possible, analyze only what is needed,
and leave the decision to the user**. New features should not turn CopyPasteBin
into a large, persistent clipboard archive.

## Status meanings

- **In progress** — approved work that is currently being prepared or tested.
- **Planned** — an accepted direction, but not a promise for a particular
  version or date.
- **Exploring** — a possibility being researched. It may change substantially
  or never become part of the product.
- **Not planned** — a deliberate product boundary unless the owner explicitly
  revisits it.

## Current public release

CopyPasteBin 1.2 is the current public stable release for GNOME Shell 50 on
Wayland. It provides local sensitive-data detection, warnings, text and image
redaction, exact low- and medium-risk exceptions, and pause controls. Its
session-only text history keeps recognized secrets and high-risk content out
of the list independently of warning-filter settings, and history saving can
be disabled without stopping analysis or the editor. Version 1.2 is available
from an Ubuntu PPA as three matching Debian packages and from GitHub Release as
the same packages or a user-local tar.gz archive.

## Planned

### Easier-to-scan menu actions in version 1.3

The GNOME menu is planned to use neutral symbolic icons aligned in one left
column for two explicit actions:

- `document-edit-symbolic` before “Edit / anonymize clipboard”;
- `image-x-generic-symbolic` before “Anonymize image”.

The text remains visible, and the complete row—not only the icon—stays
clickable. The icons do not use the green or red reserved for CopyPasteBin
states. Before implementation, their readability in light and dark themes,
alignment with status dots, and mouse and keyboard behavior must be checked
on a real GNOME Shell session.

### Easier text preparation

Planned work includes improving the built-in editor and custom rules,
including regular-expression support after safe limits and clear match review
have been designed. The goal is easier content preparation, not automatic
decisions on the user's behalf.

### Improve manual image redaction

After version 1.1, the manual image-redaction workflow may be refined in
response to real use. The core boundary remains: the user chooses a local
image, selects what to cover, and saves a new file without modifying the
original.

## Exploring

### Explicit local OCR

CopyPasteBin may explore an on-demand, local-only OCR step for reviewing text
inside a user-selected image. This is not implemented. It would require an
explicit user action and review; it would not silently monitor images or apply
automatic redaction.

### Additional desktop environments

Linux Mint Cinnamon and KDE Plasma require separate desktop adapters and real
testing. The existing command-line core is not evidence of desktop
compatibility. KDE would also need Wayland and X11 to be evaluated separately.

### Windows

A Windows version is a research direction, not an announced port or scheduled
release.

### Distribution and workflow options

Possible future work includes optional filter profiles, broader Ubuntu release
coverage, a separately reviewed GNOME Extensions submission, or separating
the detection core from desktop-specific integrations. Each option needs a
concrete user benefit before it expands the product or its maintenance
surface.

## Not planned

The current product direction does not include:

- cloud processing, accounts, synchronization, telemetry, or advertising;
- persistent storage of clipboard contents;
- silent background replacement of clipboard text;
- intercepting ordinary `Ctrl+V`, automatic pasting, or global input hooks;
- inspecting the destination application, field, window, or URL;
- bringing back the legacy polling watcher or installing an unnecessary
  always-running service.

CopyPasteBin follows the principle: **a suggestion may be automatic, but the
action is not**. Saving redacted content or changing configuration requires an
explicit user decision.

## Feedback

Public issues may be used to discuss priorities, but never attach real secrets,
private clipboard contents, private images, or production configuration.
Roadmap entries describe direction, not a guarantee that a feature will ship.
