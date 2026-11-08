# CopyPasteBin V1 — approved contract

[Polski](v1-contract.md) | **English**

## Product

CopyPasteBin V1 consists of a local analysis core and a lightweight GNOME
Shell 50 interface. The current UX is event-driven and does not poll the
clipboard. The old `wl-paste` watcher, service, and service launcher are
legacy code.

The application warns and helps the user explicitly correct text. Detection
alone does not block, delete, or modify the clipboard. An optional separate
feature can clear unchanged warning content after a selected delay.

## Input and limits

The explicit CLI accepts exactly one source: stdin, an ordinary file, or the
clipboard selected with `--clipboard`. The GNOME interface retrieves only a
text MIME type after an `owner-changed` event. Both paths require UTF-8 and
enforce a 10 MiB limit; NUL, invalid UTF-8, excess data, and an incomplete
frame block the operation.

An input file must be an ordinary file opened with `O_NOFOLLOW`. Content is
analyzed in memory and never executed. It does not enter argv, the environment,
logs, public errors, or a temporary file.

## Categories and risk

Rules cover:

- email, phone, PESEL, IBAN, payment card, recovery key, private home path, and
  IP address;
- credentials in URLs and Authorization/Basic/Bearer headers;
- private keys, OpenAI/Anthropic/Google/Stripe/AWS keys, GitHub/Slack tokens,
  JWTs, database connection strings, and secret assignments;
- token-like high-entropy strings;
- possible seed phrases and BIP-39 phrases;
- explicit amounts in 20 fiat currencies and 20 cryptocurrencies;
- bounded literal `CUSTOM_RULE` entries.

Risk levels are `critical`, `high`, `medium`, and `low`; no match is the
separate `none` value. Private keys, recovery keys, and seed phrases are
`critical`; authentication secrets are `high`; email and a valid IBAN are
`medium`; weaker heuristics and monetary amounts are `low`. A heuristic is
not proof of validity or complete detection.

PESEL requires a valid checksum and possible encoded date, IBAN requires
modulo 97, and payment cards require Luhn validation. A valid checksum does not
prove that a number exists. A BitLocker recovery key requires all 48 digits in
eight groups; every group must be within Microsoft's format range and
divisible by 11. It is `critical` and is not simultaneously reported as a
phone number. Other formats enter `RECOVERY_KEY` only with an explicit
recovery key/code/password label; there is no generic guessing of every long
identifier.

The phone heuristic does not classify valid year-month-day or day-month-year
calendar dates as phone numbers. The exception is limited to validated dates
and does not suppress a phone number beside a date. It also does not split a
maximal run of digits and separators into shorter apparent phones. A candidate
has 7–15 digits and must pass structure and bounded-context checks. An explicit
`+` prefix or parentheses remain strong signals even near an identifier
label. In a rejected run longer than 15 digits, only fragments with an explicit
phone label or their own formatting are reconsidered.

Cryptocurrency detection requires a number and an explicit ticker,
case-insensitively. A ticker by itself does not warn. Fixed lists are updated
with releases; the application does not query prices, wallets, transactions,
or a blockchain.

For 12/15/18/21/24 lowercase ASCII words, the engine distinguishes a valid
BIP-39 checksum, BIP-39 words with an invalid checksum, and a broader seed-like
structure. All remain critical risk. The local 2,048-word list is versioned
and checked by SHA-256 and structural invariants. Corruption fails closed.

No matches always means only:

> No known patterns were detected. This does not guarantee that the text is safe.

## Analysis and explicit CLI copying

An explicit analysis result includes categories, risk, and a deterministic
redacted preview. `--copy redacted` writes the redaction to the clipboard.
`--copy original` for high risk requires the one-time phrase
`COPY <operation_id>` in the same process. There is no `--force`, `--yes`,
persistent consent, or duplicate-inherited exception.

## Persistent history

Technical retention is at most 90 days and 1,000 records; the interface shows
at most eight. History may store an ID, time, source kind, destination, rule
version, size bucket, HMAC, duplicate relationship, categories, counts, risk,
and status.

It does not store original text, redacted text, or an input fragment.
Deduplication uses HMAC-SHA-256 with a random `0600` key. Every operation gets
a new ID and inherits no decision.

A GNOME event stores a stable bounded source application identifier when one
can be established reliably. It does not store window title, document name,
URL, PID, or process path. The destination of ordinary copying is `unknown`;
focus in another window is not proof of a paste.

## Event-driven GNOME backend

The extension subscribes only to `Meta.Selection::owner-changed` for the
clipboard. It has no read timer or global keyboard hook. Before transfer it
checks lock, greeter, and pause state, selects from a closed MIME list, and
enforces the input limit. After confirming `ACTIVE`, it may briefly switch the
front sheet of its local icon to light gray for 200 ms to acknowledge an owner
change. This is not an analysis result, does not alter banners, and does not
occur during pause, lock, or a self-generated editor write.

Content travels through anonymous stdin to fixed `cpb bridge observe`. The
core checks pause again, analyzes, and records metadata. Its response is at
most 2 KiB of JSON containing only version, risk, categories with counts, and
the boolean decision of the independent history policy.

An owner change whose content is identical to the last handled or currently
analyzed content is a technical duplicate. The extension recognizes it using
a SHA-256 digest held only in RAM and does not resend it to the bridge, display
a second banner, duplicate history or recent entries, or move the automatic
clearing timer. The digest is dropped on lock, logout, or extension disable.
Explicit Safe Paste intentionally bypasses this deduplication.

`none` creates no warning. `low`, `medium`, `high`, and `critical`
create content-free banners colored by level. A banner disappears after six
seconds, on manual close, when replaced, or on lock. Empty text produces a
blue informational banner and is neither analyzed nor recorded. Transfer
failure, excess data, or unconfirmed protection remains red and fail-closed.

The icon uses three local SVGs. A green back sheet means confirmed `ACTIVE`;
red means pause, transition, error, or an unconfirmed state.

## Pause

Available modes are 30 minutes, one hour, indefinite pause, and explicit
resume. While paused, the extension does not request content, analyze, warn,
or record an event. The private state contains only a mode and optional
deadline.

After automatic or manual resume, the clipboard value already present is not
analyzed retroactively. A pause set while the editor is open blocks a later
suggestion or save.

## Filter settings and recent-text policy

Each closed warning category can be enabled or disabled independently. With no
settings file, `TOKEN`, `HOME_PATH`, and `POSSIBLE_SEED_PHRASE` are
disabled; other filters, including service-specific key categories, are
enabled. The menu shows the active count and opens a scrollable window with a
checkmark for each category. Changes are saved immediately.

A disabled category creates no warning or count in persistent history and is
not replaced by a redaction suggestion. Other categories in the same text
remain active. The independent recent-text policy uses complete detections
before filters, so a recognized secret and `high` or `critical` risk do not
enter the 15-entry list even when the corresponding warning filter is
disabled. A separate high-entropy heuristic used only for this policy can omit
additional standalone strings without displaying another warning.

Filter state contains only a version, sorted disabled `Category` names, and a
closed automatic-clearing delay. The file is atomic and private and contains
no clipboard data. Invalid or extended documents fail closed. Disabling
filters is not pause and does not stop the event observer.

History saving is independent. The extension can retain up to 15 eligible
recent texts in RAM, with limits of 256 KiB per entry and 2 MiB total. A larger
text is analyzed without being added. Disabling a non-empty list requires
confirmation that states how many entries will be removed; canceling preserves
the setting and entries. An empty list causes no redundant prompt.
`history-settings.json` stores only a version and the `enabled` boolean.

The recent-entry window receives a bounded snapshot through stdin, displays a
safe preview, and returns only a closed action and content-free identifier.
Restoring checks pause again. Content is not written to disk and cannot be
restored after lock, extension disable, logout, or session end. The extension
does not run in `unlock-dialog`; unlock starts with a new empty list.
JavaScript copies, swap, hibernation, and process dumps mean this is not
cryptographic erasure.

Optional automatic clearing is disabled by default and may be set to 1, 5, or
15 minutes. A timer exists only after a warning and is tied to the current
event sequence. New copying, editing, pause, setting change, or component
disable cancels it. Pause and the unchanged sequence are checked again before
the clipboard is set to empty text.

## Editor and customizations

The GTK text editor starts only on explicit action. It receives the current
text through stdin and returns an approved result through stdout. The clipboard
changes only after **Replace clipboard**; cancel and close have no effect.

Redaction uses the same engine. Selection redaction processes only the
explicit range and is rejected if the buffer changed while analysis was
running. Match positions return through bounded JSON without matched content.
Editing removes stale markers; reanalysis is explicit. Undo has a 50-step
in-process limit. Clipboard clearing requires a second click.

The custom-rules window manages up to 32 literal markers and 32 literal
exclusions. Rules accept no regular expressions. Exclusions are
case-sensitive, remove only a detection with the identical range, and are
available only for `low` and `medium`; `high` and `critical` cannot be
excluded. Entries are stored in private `config.toml`, so the interface warns
not to use real passwords, keys, or secrets as exclusions.

The GUI has an English base and complete Polish translation. The selected
system, Polish, or English language applies to menus, banners, editors,
filters, recent entries, and customizations. It is local and does not change
data formats or detection results.

The separate image editor opens only on explicit request for a local PNG or
JPEG file. It permits manual rectangular masks and saves a new metadata-free
PNG. It does not capture the screen, monitor clipboard images, use OCR or the
network, or overwrite the source file.

## Exit and restart

**Quit CopyPasteBin** opens a modal confirmation dialog with **Cancel** as the
safe default. Only explicit confirmation disables the extension's own UUID
through fixed argv and cleans signals, transfer, editor process, banners, and
timers. It does not uninstall the application or delete persistent history.

The application launcher executes only
`/usr/bin/gnome-extensions enable copypastebin@kozlowska-anna.github.io`,
without a terminal, shell, old service, or watcher.

## Privacy and presentation

Public errors are fixed and redacted. Detection-position models have a
redacted `repr`. Terminal previews neutralize ANSI, C0/C1, and bidirectional
controls. Private channels are bounded.

The application does not use the network, intercept `Ctrl+V`, execute input,
send text, or guess the destination. It does not protect against root, another
process running as the same user, a clipboard manager, screen observation, a
compromised destination application, or false negatives.

## Legacy watcher and lifecycle

`cpb watch start`, `cpb service ...`, and `cpb launcher setup` are
fail-closed legacy code covered by tests. Polling `wl-paste` on GNOME Shell
50.1 used a temporary Wayland surface, stole focus, and closed context menus.
The legacy service must remain inactive and its former launcher absent. This
path is not repaired by a longer interval, retries, stderr parsing, or exit
code guessing.

## Outside V1

Cloud services, device synchronization, OCR, automatic clipboard-image
processing, a browser extension, automatic modification of every copy,
auto-paste, auto-send, a global keyboard hook, and any guarantee of detecting
all sensitive data. The manual local PNG/JPEG editor is part of V1 but runs
only on request and does not monitor the clipboard.

Version 1.2.1 is prepared for distribution through the stable PPA for Ubuntu
26.04 and GitHub Release, with a user-local tar.gz archive as an alternative.
GNOME Extensions publication and a separately confined core package require
later review. The extension has a stable public UUID and an English base
interface with a Polish translation.
