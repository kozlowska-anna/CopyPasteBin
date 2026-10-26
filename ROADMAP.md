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

CopyPasteBin 1.1 is the current public stable release. It provides local
sensitive-data detection, warnings, text redaction, exact low- and medium-risk
exceptions, Safe Paste, pause controls, and session-only recent clipboard text
for GNOME Shell 50 on Wayland. Version 1.1 adds manual local PNG/JPEG redaction,
refreshed application and panel icons, pause-control refinements, and two
installation formats from the same source set: a Debian package and a
user-local tar.gz archive.

## Planned

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

Possible future work includes standard Debian source packaging, DEP-5
copyright metadata, a signed package repository, optional filter profiles, or
separating the detection core from desktop-specific integrations. Each option
needs a concrete user benefit before it expands the product or its maintenance
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
