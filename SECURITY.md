# CopyPasteBin V1 Security Model

[Polski](docs/security.pl.md) | **English**

## Protected data

Original text, personal and financial data, secrets, redacted output, and the
HMAC key must not enter persistent history, logs, errors, `repr`, argv, the
environment, or temporary files. The explicit exception is a bounded list of
recent text entries held only in the extension's session memory. Terminal
preview neutralizes ANSI, C0/C1, and bidirectional control characters.

The current desktop path is the event-driven GNOME Shell 50 extension. The old
`wl-paste` watcher, systemd service, and former launcher are legacy code and
must remain inactive.

## Technical boundaries

- no network, cloud service, automatic sending, or automatic pasting;
- no `shell=True`, `eval`, `exec`, execution of input, or opening URLs;
- no global keyboard hook and no interception of `Ctrl+V`;
- one `Super+Shift+V` shortcut registered through the standard
  `Main.wm.addKeybinding`, active only in `Shell.ActionMode.NORMAL`;
- UTF-8 input, a 10 MiB limit, and rejection of NUL and excess data;
- ordinary input files opened with `O_NOFOLLOW`;
- stdin/stdout instead of text in argv, environment variables, or temporary
  files;
- history uses HMAC-SHA-256 rather than a plain content hash;
- filter settings store only closed category names and the selected automatic
  clearing delay;
- the contents of an explicitly created custom rule are an exception because
  they must be stored locally; the interface therefore warns against entering
  a real secret;
- `high` and `critical` levels have no persistent or automatic exception;
- public errors are fixed messages and do not expose the underlying exception.

CopyPasteBin does not protect against root, another process running as the same
user, a system clipboard manager, screen observation, a compromised destination
application, false negatives, or copies left in interpreter memory.

## GNOME event and transfer

The extension reacts only to
`Meta.SelectionType.SELECTION_CLIPBOARD::owner-changed`. Before transfer it
checks the lock screen, greeter, and full pause state. It accepts a closed list
of text MIME types and retrieves at most 10 MiB plus one byte.

The event source is a bounded application identifier. CopyPasteBin does not
store the window title, document name, URL, PID, process path, or an arbitrary
unbounded value supplied by an application.

The frame sent to `cpb bridge observe` travels through anonymous stdin and
contains only the bounded identifier and text. The bridge rejects an invalid
length, incomplete frame, excess data, invalid UTF-8, NUL, and empty text, then
checks the pause state again.

The stdout response is limited to 2 KiB and uses closed JSON containing only
the version, risk level, and categories with counts. It contains no text,
redaction, match positions, or operation ID. The extension validates the full
response before displaying a banner.

A successful zero-length text MIME transfer is not sent to the bridge and does
not create history. It displays only a blue empty-clipboard notice. A failed
transfer or limit violation remains a fail-closed error.

## History, session cache, and deduplication

History stores only metadata, a technical HMAC, and the duplicate relation. It
does not store the original, redacted output, or a supposedly harmless
fragment. The view is limited to 8 entries; technical retention is 90 days and
1,000 records.

The private state directory has mode `0700`; the database, HMAC key, and
pause state have mode `0600`. Secure stores reject symlinks, a foreign owner,
and incorrect permissions. The HMAC key is random and local.

The destination of ordinary copying remains `unknown`. A focus change is not
proof of a paste and does not supplement history.

The extension additionally retains up to 15 recent text entries, with limits
of 256 KiB per entry and 2 MiB in total. An entry is created only after the
bridge response has been validated, so a pause, locked screen, empty or invalid
transfer, and analysis failure do not add content. The text is not sent to
Python again and does not enter the database or a state file.

A separate GTK window receives a temporary binary snapshot through stdin. It
returns only a closed action and a content-free entry identifier through
stdout; errors are suppressed and redacted. Restoring an entry checks pause
and screen lock again. Disabling the extension closes the window and drops
references to the entries. JavaScript, swap, hibernation, and process dumps
mean this is not cryptographic erasure and cannot guarantee that bytes never
touch storage.

The extension intentionally does not declare GNOME `unlock-dialog` mode.
Locking the screen disables it through the standard GNOME lifecycle, and
`disable()` clears the RAM list. After unlocking, a new and initially empty
list is created. This keeps CPB code inactive on the lock screen at the cost of
losing the session cache.

## Detection

Risk levels are ordered `critical > high > medium > low`; no match is the
separate `none` state. Private keys, recovery keys, and seed phrases are
`critical`; recognized authentication secrets are `high`; email and a valid
IBAN are `medium`; weaker heuristics and monetary amounts are `low`.

The secret library has separate, disableable categories for OpenAI, Anthropic,
and Google keys, GitHub and Slack tokens, Stripe keys, AWS access identifiers,
JWTs, and database connection strings. A JWT must have three segments and a
decodable JSON header with an algorithm other than `none`. Rules work offline,
do not try to use a key, and do not test whether it is active. The general
entropy heuristic remains a supplementary safeguard and can produce false
positives.

The BIP-39 list is a local resource. The code checks its SHA-256, exactly 2,048
unique words, ordering, and the phrase checksum. Corruption fails closed; an
invalid phrase checksum is still treated as high risk.

A BitLocker recovery password is recognized only as a complete 48-digit value
in eight groups. Every group must be no greater than 720885 and divisible by
11, following Microsoft's format. The match is critical risk and occupies the
whole range before the phone heuristic runs. Disabling `RECOVERY_KEY` does
not expose overlapping phone matches again. Other formats may enter this
category only with an explicit recovery key/code/password label or the Polish
label “klucz odzyskiwania”. An unlabeled string is not classified as a recovery
key from length or entropy alone.

Amounts for 20 supported cryptocurrencies require a number and an explicit
ticker. The rule does not connect to a network, query exchange rates or a
blockchain, and does not interpret a ticker alone as financial data. The list
of 20 fiat currencies comes from a closed set of codes and does not trigger
conversion or rate downloads.

PESEL passes its checksum and encoded-date validation, IBAN passes modulo 97,
and payment card numbers pass the Luhn algorithm. These checks reduce false
positives but do not confirm that a number exists, is active, or belongs to a
particular person.

The phone heuristic first captures the maximal sequence of digits and
supported separators, then validates 7–15 digits, `+` placement, parentheses,
grouping, and short context. It does not cut shorter phone-like fragments from
a long identifier. Identifier labels suppress only ambiguous formats; a number
with a `+` prefix or parentheses is still analyzed. This is an offline
heuristic, not confirmation that the number exists or has a particular owner.
Within a rejected sequence longer than 15 digits, the engine recovers
space-separated fragments only when there is an explicit phone label or the
fragments have their own formatting. An identifier label disables that second
pass. The engine does not arbitrarily combine short groups into possible phone
numbers.

Custom rules are literal markers with count and length limits. Each rule can
remain stored while being disabled by a boolean flag. Rules accept neither
regular expressions nor code. Separate literal exclusions intentionally weaken
built-in rules only for a detection with exactly the same range and stored
category. Only `low` and `medium` categories are allowed; `high` and
`critical` are rejected by the core independently of the GUI. Exclusions are
case-sensitive, do not disable a whole category, and do not hide an adjacent
match. The interface warns against excluding real sensitive data.

The rules editor runs only after an explicit action, transfers bounded JSON
through stdin/stdout, and atomically saves `config.toml` with mode `0600`
inside a `0700` directory. Rule contents do not enter history or error
messages.

The exclusion button on a `low` or `medium` banner does not select or save a
hidden value; it opens the clipboard editor. The editor displays positions in
the detected text. A single click inside a `low` or `medium` match selects
the known complete range of 3–128 characters without control characters and
shows a local popover with the category. Pointer movement beyond the defined
tolerance remains ordinary selection and does not trigger the action. The
popover opens a modal confirmation with cancel as the default action and a
visually emphasized add action. Before saving, the editor checks the text
revision, range, category, risk, and literal again. The value is sent to the
bounded `ui exclusion-add` command through stdin, never through argv, the
environment, logs, or a temporary file. The response contains only a closed
status without content. The core rechecks the category, length, control
characters, conflicts, and limit; `high` and `critical` are rejected
independently of the GUI.

Configuration V3 stores the literal, category, and enabled state for each
exclusion. V2 migration is conservative: an old literal is imported only when
it produces one full-range `low` or `medium` match by itself. Ambiguous old
entries and high- or critical-risk entries are ignored and removed on the next
explicit save. Reading, migration, and writing preserve the limit, atomic
`0600` file, `0700` directory, and refusal to operate on symlinks.

The GUI language selection is separate state with closed values `system`,
`pl`, and `en`. Private `language.json` contains no clipboard text, rules,
or history and is subject to the same owner, permission, and symlink checks as
other state files. Window processes receive only the effective `pl` or `en`
code.

No match is not a declaration of safety.

## Safe Paste

`Super+V` remains GNOME's shortcut for the message tray, so CopyPasteBin's
explicit action uses `Super+Shift+V`. The extension registers one keybinding
name from its own closed GSettings schema. It does not use a global hook,
`grab_accelerator`, key emulation, or interception of `Ctrl+V`. `disable()`
always removes the keybinding, cancels active analysis, and releases its
process.

The action checks lock/greeter and pause state before reading and again before
showing a result. Text travels only through stdin to `cpb ui detections`; the
response contains only bounded positions, categories, and levels. `none`
does not change the clipboard. Other levels open the existing editor, which
locally requests a redaction suggestion; the result exists in its memory and
returns to the extension only after an explicit save. `high` and `critical`
have no exclusion in this path. Canceling, an error, a pause, or screen lock
does not write to the clipboard.

The feature does not paste and does not determine the destination application,
window title, document name, or URL. It does not increase the limit of 15
recent RAM entries and does not create a new daemon, polling timer, or
persistent content history.

## Pause

Pause is a read boundary, not notification muting. For 30 minutes, one hour, or
until manual resume, the extension does not request content, analyze, warn, or
record events.

Pause state contains only a version, mode, and optional deadline. After resume,
the value already present in the clipboard is not analyzed retroactively.
Pause is checked before transfer, inside the bridge, and before opening the
editor, suggesting a redaction, or saving.

## Banner and icon

The banner is a local `St` actor. It displays only closed category names and
counts and does not use system `notify-send` on the current path. It
disappears after 6 seconds, when closed manually, when replaced by another
event, or when the screen locks.

Disabling removes the banner, timer, and session-mode signal. Do not use
`affectsInputRegion` with `Main.layoutManager.addChrome` on GNOME Shell
50.1; this unsupported parameter previously caused an extension error.

The green icon variant appears only after confirmed `ACTIVE`. Pause,
transition, and error remain red and fail closed. After `ACTIVE` is confirmed,
a clipboard owner change may switch only the local SVG variant to one with a
light-gray front sheet for 200 ms. This signal carries no content, category, or
analysis result, does not occur on the lock screen, and is cleaned up with the
extension. It does not replace risk banners.

## Editor and clipboard writes

The GTK editor starts only after an explicit action and receives text through
stdin. Its result returns through stdout to the extension, which remains
responsible for writing the clipboard. Canceling or closing changes nothing.

The redaction suggestion uses the same engine through `cpb ui redact`.
Selection mode sends only the explicitly selected fragment through the same
bounded channel and replaces only that range. If the text changes before
analysis finishes, the result is rejected instead of being applied to a stale
position. The change is grouped as one undo step.

Match positions for explicit highlighting return through separate bounded JSON
without matched content. Editing removes stale markers. Text tools and bounded
undo operate only in editor-process memory. Clearing requires a second click.
A pause set while the editor is open blocks a later suggestion or save.

The extension skips one self-generated event after a write to avoid an
additional history entry or warning. The mechanism has a bounded timeout and
is cleaned up on disable.

Colored markers use explicit GTK4 `TextTag` objects added to the buffer's tag
table; a failure to activate the window must not be treated as a visible
editor. The process is cleaned up after every communication. Clicking again
while it is running sends a fixed `SIGUSR1`, handled locally by the editor
only as a request to `present()` the existing window; it carries no data.

## Filter settings

Filter state is private `0600` JSON inside the `0700` state directory. It
contains only a version, a canonical list of disabled `Category` values, and
one closed clearing delay: 0, 60, 300, or 900 seconds. With no file,
`TOKEN`, `HOME_PATH`, and `POSSIBLE_SEED_PHRASE` are disabled by default;
all other categories are enabled. An unknown category, duplicate, excess data, symlink,
foreign owner, or incorrect permissions blocks reading and analysis for that
flow instead of guessing the configuration.

UI commands use closed category arguments and `on|off`; they accept no
clipboard text. The response is limited to 2 KiB and contains the complete
fixed list with boolean values. A separate GTK process displays only public
labels, checkmarks, and a count; it writes each change separately and blocks
further clicks until it receives a validated response.

Deliberately disabling a category weakens detection coverage according to the
user's decision. The count is visible in the menu and full state in the
window; the setting applies consistently to the backend, explicit analysis,
and redaction. It does not remove earlier entries and is not equivalent to
pause.

## Optional automatic clearing

The default is 0, meaning no automatic clipboard change. After the user
explicitly selects 1, 5, or 15 minutes, a timer is created for every result
from `low` through `critical`. The extension retains only the event sequence
number and timer, not content or its hash. Any clipboard owner change, explicit
edit, setting change, pause, or extension disable cancels the timer. Immediately
before clearing, pause and the sequence number are checked again; only then is
the clipboard set to empty text. This feature does not provide cryptographic
memory erasure or control over copies saved by other clipboard managers.

## Exit and launcher

Exit requires a second click within 8 seconds. It uses the fixed
`/usr/bin/gnome-extensions disable <own UUID>` command without a shell or user
data. Normal `disable()` disconnects signals, cancels transfer, terminates the
editor, and removes UI and timers.

The current launcher executes only `/usr/bin/gnome-extensions enable
copypastebin@kozlowska-anna.github.io`, has `Terminal=false`, and accepts no
files or URIs. It does not start the old service, `watch start`, sudo, or a
dynamic command.

The installer persists the same public UUID in `org.gnome.shell
enabled-extensions` because GNOME may not yet recognize a newly copied
extension in the current session. The helper uses local `Gio.Settings`,
preserves every unrelated entry, removes only the development UUID
`copypastebin@local`, and does not print the list it reads. It uses no network,
service, delay, or clipboard access. `--no-enable` skips this change.

## Explicit CLI

Explicit clipboard reading and writing in the CLI use fixed argv,
`shell=False`, bounded stdout, and text supplied for writing only through
stdin. A high-risk original requires a one-time constant-time comparison with
`COPY <operation_id>`; refusal and failure update only status metadata.

## Legacy code

`cpb watch start`, `cpb service ...`, and `cpb launcher setup` are an
earlier architecture covered by tests. Polling `wl-paste` on GNOME Shell 50.1
used a temporary Wayland surface, stole focus, and closed context menus. It is
therefore not a current product mode.

The legacy watcher retains fail-closed behavior, fixed argv, bounded startup
grace, a private `flock`, redacted errors, and `Restart=no`, but it must not
run in parallel or be restored by the former launcher. The old service must
remain stopped and absent. This path is not repaired by a longer interval,
more retries, parsing stderr, or guessing exit codes.

The historical lifecycle contract remains in code and tests but is not an
alternative mode of the current product.

## Publication

The extension has a stable public UUID and English base messages with a Polish
translation. The first public release is distributed as a local offline
archive with an external SHA-256 checksum. Publication on GNOME Extensions and
separate confined packaging of the core require later review and are outside
the scope of 1.0. The project is licensed under `GPL-3.0-or-later`, and the
BSD-3-Clause notice for BIP-39 data is preserved in the distribution. Future
work must not weaken the privacy boundaries described above.
