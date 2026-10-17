#!/usr/bin/env bash
set -Eeuo pipefail

readonly UUID="copypastebin@kozlowska-anna.github.io"
readonly LEGACY_UUID="copypastebin@local"
readonly WINDOW_APPLICATION_IDS=(
    "io.github.copypastebin.Editor"
    "io.github.copypastebin.FilterEditor"
    "io.github.copypastebin.RulesEditor"
    "io.github.copypastebin.RecentClipboard"
    "io.github.copypastebin.About"
)
readonly REQUIRED_SHELL_MAJOR="50"
readonly SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
readonly PAYLOAD_DIR="$SCRIPT_DIR/payload"
readonly CHECKSUM_FILE="$SCRIPT_DIR/SHA256SUMS"
readonly APP_DIR="$HOME/.local/share/copypastebin"
readonly VENV_DIR="$APP_DIR/venv"
readonly EXTENSIONS_DIR="$HOME/.local/share/gnome-shell/extensions"
readonly EXTENSION_DIR="$EXTENSIONS_DIR/$UUID"
readonly LEGACY_EXTENSION_DIR="$EXTENSIONS_DIR/$LEGACY_UUID"
readonly APPLICATIONS_DIR="$HOME/.local/share/applications"
readonly LAUNCHER_PATH="$APPLICATIONS_DIR/copypastebin.desktop"
readonly ICONS_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
readonly ICON_PATH="$ICONS_DIR/copypastebin.svg"

CHECK_ONLY=false
ENABLE_AFTER_INSTALL=true
VENV_BACKUP=""
EXTENSION_BACKUP=""
LEGACY_EXTENSION_BACKUP=""
LEGACY_MIGRATED=false
TRANSACTION_STARTED=false
VENV_INSTALL_STARTED=false
EXTENSION_INSTALL_STARTED=false
INSTALL_COMMITTED=false

usage() {
    cat <<'EOF'
Użycie:
  ./install.sh [--check-only] [--no-enable]

  --check-only  Sprawdź zgodność i integralność pakietu bez instalowania.
  --no-enable   Zainstaluj bez zapisywania automatycznego włączenia rozszerzenia.
EOF
}

fail() {
    printf 'CopyPasteBin: %s\n' "$1" >&2
    exit 1
}

note() {
    printf '%s\n' "$1"
}

safe_remove_tree() {
    local path="$1"
    case "$path" in
        "$VENV_DIR"|"$APP_DIR"/venv.backup.*|\
        "$EXTENSION_DIR"|"$EXTENSIONS_DIR"/$UUID.backup.*|\
        "$LEGACY_EXTENSION_DIR"|"$EXTENSIONS_DIR"/$LEGACY_UUID.migration-backup.*)
            rm -rf -- "$path"
            ;;
        *)
            fail "odmowa usunięcia nieoczekiwanej ścieżki"
            ;;
    esac
}

rollback() {
    local exit_code=$?
    if ! $TRANSACTION_STARTED || $INSTALL_COMMITTED; then
        return
    fi
    trap - EXIT INT TERM
    if $VENV_INSTALL_STARTED && [[ -e "$VENV_DIR" || -L "$VENV_DIR" ]]; then
        safe_remove_tree "$VENV_DIR"
    fi
    if [[ -n "$VENV_BACKUP" && -d "$VENV_BACKUP" ]]; then
        mv -- "$VENV_BACKUP" "$VENV_DIR"
    fi
    if $EXTENSION_INSTALL_STARTED && [[ -e "$EXTENSION_DIR" || -L "$EXTENSION_DIR" ]]; then
        safe_remove_tree "$EXTENSION_DIR"
    fi
    if [[ -n "$EXTENSION_BACKUP" && -d "$EXTENSION_BACKUP" ]]; then
        mv -- "$EXTENSION_BACKUP" "$EXTENSION_DIR"
    fi
    if [[ -n "$LEGACY_EXTENSION_BACKUP" && -d "$LEGACY_EXTENSION_BACKUP" ]]; then
        mv -- "$LEGACY_EXTENSION_BACKUP" "$LEGACY_EXTENSION_DIR"
    fi
    printf 'CopyPasteBin: instalacja nie powiodła się; poprzednią wersję przywrócono.\n' >&2
    exit "$exit_code"
}

for argument in "$@"; do
    case "$argument" in
        --check-only) CHECK_ONLY=true ;;
        --no-enable) ENABLE_AFTER_INSTALL=false ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; fail "nieznana opcja: $argument" ;;
    esac
done

[[ ${EUID:-$(id -u)} -ne 0 ]] || fail "nie uruchamiaj instalatora przez sudo ani jako root"
[[ -n "${HOME:-}" && "$HOME" = /* && "$HOME" != "/" ]] || fail "nieprawidłowy katalog HOME"
[[ ! -L "$APP_DIR" ]] || fail "$APP_DIR jest dowiązaniem symbolicznym"
[[ ! -L "$EXTENSION_DIR" ]] || fail "$EXTENSION_DIR jest dowiązaniem symbolicznym"
[[ ! -L "$LEGACY_EXTENSION_DIR" ]] || fail "$LEGACY_EXTENSION_DIR jest dowiązaniem symbolicznym"
[[ ! -L "$LAUNCHER_PATH" ]] || fail "$LAUNCHER_PATH jest dowiązaniem symbolicznym"
[[ ! -L "$ICON_PATH" ]] || fail "$ICON_PATH jest dowiązaniem symbolicznym"
for application_id in "${WINDOW_APPLICATION_IDS[@]}"; do
    window_launcher="$APPLICATIONS_DIR/$application_id.desktop"
    [[ ! -L "$window_launcher" ]] || fail "$window_launcher jest dowiązaniem symbolicznym"
done

required_files=("$CHECKSUM_FILE" "$PAYLOAD_DIR/copypastebin.desktop" \
    "$PAYLOAD_DIR/copypastebin.svg" "$PAYLOAD_DIR/$UUID/metadata.json" \
    "$PAYLOAD_DIR/$UUID/schemas/gschemas.compiled" \
    "$PAYLOAD_DIR/persist-extension-enablement.js")
for application_id in "${WINDOW_APPLICATION_IDS[@]}"; do
    required_files+=("$PAYLOAD_DIR/$application_id.desktop")
done
for required in "${required_files[@]}"; do
    [[ -f "$required" && ! -L "$required" ]] || fail "pakiet jest niekompletny: ${required#$SCRIPT_DIR/}"
done

command -v sha256sum >/dev/null 2>&1 || fail "brakuje programu sha256sum"
if [[ -n "$(find "$PAYLOAD_DIR" -type l -print -quit)" ]]; then
    fail "payload nie może zawierać dowiązań symbolicznych"
fi
listed_files=0
while IFS= read -r checksum_line || [[ -n "$checksum_line" ]]; do
    [[ "$checksum_line" =~ ^[0-9a-f]{64}\ \ payload/[^/].*$ ]] || \
        fail "nieprawidłowy wpis w SHA256SUMS"
    checksum_path="${checksum_line:66}"
    [[ "$checksum_path" != *".."* ]] || fail "nieprawidłowa ścieżka w SHA256SUMS"
    [[ -f "$SCRIPT_DIR/$checksum_path" && ! -L "$SCRIPT_DIR/$checksum_path" ]] || \
        fail "brak zwykłego pliku wymienionego w SHA256SUMS"
    listed_files=$((listed_files + 1))
done < "$CHECKSUM_FILE"
actual_files="$(find "$PAYLOAD_DIR" -type f | wc -l)"
[[ "$listed_files" -eq "$actual_files" ]] || fail "lista sum nie obejmuje całego payloadu"
(
    cd -- "$SCRIPT_DIR"
    sha256sum --check --strict SHA256SUMS
) >/dev/null || fail "kontrola integralności pakietu nie powiodła się"

mapfile -t wheels < <(find "$PAYLOAD_DIR" -maxdepth 1 -type f -name 'copypastebin-*.whl' -print)
[[ ${#wheels[@]} -eq 1 ]] || fail "pakiet musi zawierać dokładnie jeden wheel CopyPasteBin"
readonly WHEEL_PATH="${wheels[0]}"

command -v python3 >/dev/null 2>&1 || fail "brakuje Python 3"
python3 - <<'PY' || fail "wymagany jest Python 3.11 lub nowszy"
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
python3 -c 'import venv' >/dev/null 2>&1 || fail "brakuje modułu venv dla Python 3"

for executable in /usr/bin/gnome-shell /usr/bin/gnome-extensions /usr/bin/gjs; do
    [[ -x "$executable" ]] || fail "brakuje wymaganego programu: $executable"
done

shell_version="$(/usr/bin/gnome-shell --version 2>/dev/null || true)"
shell_major="$(printf '%s\n' "$shell_version" | sed -nE 's/.* ([0-9]+)(\.[0-9]+)*$/\1/p')"
[[ "$shell_major" == "$REQUIRED_SHELL_MAJOR" ]] || fail \
    "wymagany jest GNOME Shell $REQUIRED_SHELL_MAJOR; wykryto: ${shell_version:-nieznaną wersję}"

/usr/bin/gjs -c "imports.gi.versions.Gtk = '4.0'; imports.gi.Gtk; imports.gi.GioUnix" \
    >/dev/null 2>&1 || fail "brakuje GTK 4 lub bibliotek GObject wymaganych przez edytor"

if [[ -n "${XDG_SESSION_TYPE:-}" && "${XDG_SESSION_TYPE,,}" != "wayland" ]]; then
    fail "CopyPasteBin wymaga sesji GNOME na Waylandzie; bieżąca sesja to $XDG_SESSION_TYPE"
fi

note "Kontrola zgodności: OK"
note "GNOME Shell: $shell_version"
note "Python: $(python3 -c 'import platform; print(platform.python_version())')"

if $CHECK_ONLY; then
    note "Nie wprowadzono żadnych zmian."
    exit 0
fi

mkdir -p -- "$APP_DIR" "$EXTENSIONS_DIR" "$APPLICATIONS_DIR" "$ICONS_DIR"
chmod 700 -- "$APP_DIR"

timestamp="$(date -u +%Y%m%d%H%M%S)"
TRANSACTION_STARTED=true
trap rollback EXIT
trap 'exit 130' INT TERM
if [[ -e "$VENV_DIR" || -L "$VENV_DIR" ]]; then
    [[ -d "$VENV_DIR" && ! -L "$VENV_DIR" ]] || fail "$VENV_DIR nie jest zwykłym katalogiem"
    VENV_BACKUP="$APP_DIR/venv.backup.$timestamp.$$"
    mv -- "$VENV_DIR" "$VENV_BACKUP"
fi
if [[ -e "$EXTENSION_DIR" || -L "$EXTENSION_DIR" ]]; then
    [[ -d "$EXTENSION_DIR" && ! -L "$EXTENSION_DIR" ]] || fail "$EXTENSION_DIR nie jest zwykłym katalogiem"
    EXTENSION_BACKUP="$EXTENSIONS_DIR/$UUID.backup.$timestamp.$$"
    mv -- "$EXTENSION_DIR" "$EXTENSION_BACKUP"
fi
if [[ -e "$LEGACY_EXTENSION_DIR" || -L "$LEGACY_EXTENSION_DIR" ]]; then
    [[ -d "$LEGACY_EXTENSION_DIR" && ! -L "$LEGACY_EXTENSION_DIR" ]] || \
        fail "$LEGACY_EXTENSION_DIR nie jest zwykłym katalogiem"
    LEGACY_EXTENSION_BACKUP="$EXTENSIONS_DIR/$LEGACY_UUID.migration-backup.$timestamp.$$"
    mv -- "$LEGACY_EXTENSION_DIR" "$LEGACY_EXTENSION_BACKUP"
    LEGACY_MIGRATED=true
fi
VENV_INSTALL_STARTED=true
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --no-index --no-deps --disable-pip-version-check \
    "$WHEEL_PATH" >/dev/null
[[ -x "$VENV_DIR/bin/cpb" ]] || fail "nie powstał oczekiwany program cpb"
"$VENV_DIR/bin/cpb" --help >/dev/null

EXTENSION_INSTALL_STARTED=true
cp -a -- "$PAYLOAD_DIR/$UUID" "$EXTENSION_DIR"
chmod -R u=rwX,go= -- "$EXTENSION_DIR"

launcher_tmp="$LAUNCHER_PATH.tmp.$$"
icon_tmp="$ICON_PATH.tmp.$$"
install -m 0600 -- "$PAYLOAD_DIR/copypastebin.desktop" "$launcher_tmp"
install -m 0600 -- "$PAYLOAD_DIR/copypastebin.svg" "$icon_tmp"
mv -f -- "$launcher_tmp" "$LAUNCHER_PATH"
mv -f -- "$icon_tmp" "$ICON_PATH"
for application_id in "${WINDOW_APPLICATION_IDS[@]}"; do
    window_launcher="$APPLICATIONS_DIR/$application_id.desktop"
    window_launcher_tmp="$window_launcher.tmp.$$"
    install -m 0600 -- "$PAYLOAD_DIR/$application_id.desktop" "$window_launcher_tmp"
    mv -f -- "$window_launcher_tmp" "$window_launcher"
done

if [[ -n "$VENV_BACKUP" ]]; then
    safe_remove_tree "$VENV_BACKUP"
    VENV_BACKUP=""
fi
if [[ -n "$EXTENSION_BACKUP" ]]; then
    safe_remove_tree "$EXTENSION_BACKUP"
    EXTENSION_BACKUP=""
fi
/usr/bin/gnome-extensions disable "$LEGACY_UUID" >/dev/null 2>&1 || true
if [[ -n "$LEGACY_EXTENSION_BACKUP" ]]; then
    safe_remove_tree "$LEGACY_EXTENSION_BACKUP"
    LEGACY_EXTENSION_BACKUP=""
fi

INSTALL_COMMITTED=true
trap - EXIT INT TERM

if $ENABLE_AFTER_INSTALL; then
    if /usr/bin/gjs "$PAYLOAD_DIR/persist-extension-enablement.js" \
            >/dev/null 2>&1; then
        /usr/bin/gnome-extensions enable "$UUID" >/dev/null 2>&1 || true
        note "Rozszerzenie zostało trwale włączone na następne logowanie."
    else
        note "Nie udało się zapisać włączenia rozszerzenia; po ponownym zalogowaniu uruchom CopyPasteBin z menu aplikacji."
    fi
fi

note ""
note "CopyPasteBin został zainstalowany."
if $LEGACY_MIGRATED; then
    note "Poprzedni UUID rozszerzenia został bezpiecznie zastąpiony publicznym UUID."
fi
note "Wyloguj się i zaloguj ponownie do sesji GNOME Wayland."
note "Po zalogowaniu CopyPasteBin powinien uruchomić się automatycznie."
note "Ustawienia i historia użytkownika nie zostały zmienione."
