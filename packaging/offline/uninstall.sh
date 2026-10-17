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
readonly APP_DIR="$HOME/.local/share/copypastebin"
readonly EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/$UUID"
readonly LEGACY_EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/$LEGACY_UUID"
readonly LAUNCHER_PATH="$HOME/.local/share/applications/copypastebin.desktop"
readonly ICON_PATH="$HOME/.local/share/icons/hicolor/scalable/apps/copypastebin.svg"

if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
    cat <<'EOF'
Użycie: ./uninstall.sh

Usuwa program, rozszerzenie, launcher i ikonę CopyPasteBin.
Nie usuwa ustawień ani historii użytkownika.
EOF
    exit 0
fi
[[ $# -eq 0 ]] || { printf 'Nieznana opcja. Użyj --help.\n' >&2; exit 2; }
[[ ${EUID:-$(id -u)} -ne 0 ]] || { printf 'Nie uruchamiaj przez sudo ani jako root.\n' >&2; exit 1; }
[[ -n "${HOME:-}" && "$HOME" = /* && "$HOME" != "/" ]] || { printf 'Nieprawidłowy HOME.\n' >&2; exit 1; }

if [[ -x /usr/bin/gnome-extensions ]]; then
    /usr/bin/gnome-extensions disable "$UUID" >/dev/null 2>&1 || true
    /usr/bin/gnome-extensions disable "$LEGACY_UUID" >/dev/null 2>&1 || true
fi

rm -rf -- "$APP_DIR" "$EXTENSION_DIR" "$LEGACY_EXTENSION_DIR"
rm -f -- "$LAUNCHER_PATH" "$ICON_PATH"
for application_id in "${WINDOW_APPLICATION_IDS[@]}"; do
    rm -f -- "$HOME/.local/share/applications/$application_id.desktop"
done

printf '%s\n' \
    'CopyPasteBin został odinstalowany.' \
    'Ustawienia i historia pozostały na komputerze.' \
    "Ustawienia: $HOME/.config/copypastebin" \
    "Historia: $HOME/.local/state/copypastebin"
