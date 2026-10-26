#!/usr/bin/env bash
set -Eeuo pipefail

readonly UUID="copypastebin@kozlowska-anna.github.io"
readonly LEGACY_UUID="copypastebin@local"
readonly GNOME_EXTENSIONS_BIN="${CPB_DIAGNOSTIC_GNOME_EXTENSIONS_BIN:-/usr/bin/gnome-extensions}"
readonly GNOME_SHELL_BIN="${CPB_DIAGNOSTIC_GNOME_SHELL_BIN:-/usr/bin/gnome-shell}"
readonly GSETTINGS_BIN="${CPB_DIAGNOSTIC_GSETTINGS_BIN:-/usr/bin/gsettings}"

usage() {
    cat <<'EOF'
Użycie:
  ./diagnose-first-activation.sh

Uruchom po pierwszym ponownym zalogowaniu po świeżej instalacji, zanim
uruchomisz CopyPasteBin z menu aplikacji. Test tylko odczytuje techniczny stan
GNOME. Nie odczytuje schowka ani prywatnych danych CopyPasteBin i niczego nie
zmienia.
EOF
}

case "${1:-}" in
    "") ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
    printf '%s\n' "CopyPasteBin: uruchom diagnostykę jako zwykły użytkownik, bez sudo." >&2
    exit 1
fi
if [[ -z "${HOME:-}" || "$HOME" != /* || "$HOME" == "/" ]]; then
    printf '%s\n' "CopyPasteBin: nieprawidłowy katalog HOME." >&2
    exit 1
fi

safe_environment_value() {
    local value="${1:-unknown}"
    if [[ "$value" =~ ^[[:alnum:]_.:+-]{1,80}$ ]]; then
        printf '%s' "$value"
    else
        printf '%s' "unknown"
    fi
}

command_state() {
    local path="$1"
    if [[ "$path" = /* && -x "$path" ]]; then
        printf '%s' "available"
    else
        printf '%s' "unavailable"
    fi
}

contains_uuid() {
    local content="$1"
    local uuid="$2"
    if grep -Fqx -- "$uuid" <<<"$content"; then
        printf '%s' "true"
    else
        printf '%s' "false"
    fi
}

setting_contains_uuid() {
    local content="$1"
    local uuid="$2"
    if grep -Fq -- "$uuid" <<<"$content"; then
        printf '%s' "true"
    else
        printf '%s' "false"
    fi
}

extension_dir="$HOME/.local/share/gnome-shell/extensions/$UUID"
if [[ -L "$extension_dir" ]]; then
    extension_directory="symlink"
elif [[ -d "$extension_dir" ]]; then
    extension_directory="present"
else
    extension_directory="missing"
fi

shell_command_state="$(command_state "$GNOME_SHELL_BIN")"
extensions_command_state="$(command_state "$GNOME_EXTENSIONS_BIN")"
gsettings_command_state="$(command_state "$GSETTINGS_BIN")"

shell_version="unavailable"
if [[ "$shell_command_state" == "available" ]]; then
    shell_output="$(LC_ALL=C "$GNOME_SHELL_BIN" --version 2>/dev/null || true)"
    if [[ "$shell_output" =~ ^GNOME[[:space:]]Shell[[:space:]][0-9]+([.][0-9]+)*$ ]]; then
        shell_version="$shell_output"
    fi
fi

info_result="unavailable"
info_state="unknown"
listed_result="unavailable"
listed_uuid="unknown"
listed_legacy_uuid="unknown"
enabled_list_result="unavailable"
enabled_uuid="unknown"
enabled_legacy_uuid="unknown"
if [[ "$extensions_command_state" == "available" ]]; then
    set +e
    info_output="$(LC_ALL=C "$GNOME_EXTENSIONS_BIN" info "$UUID" 2>/dev/null)"
    info_exit=$?
    set -e
    if [[ $info_exit -eq 0 ]]; then
        info_result="success"
        parsed_state="$(sed -nE 's/^[[:space:]]*State:[[:space:]]*([A-Z_-]+)[[:space:]]*$/\1/p' <<<"$info_output" | head -n 1)"
        if [[ -n "$parsed_state" ]]; then
            info_state="$parsed_state"
        fi
    else
        info_result="not-found-or-error"
    fi

    set +e
    listed_output="$(LC_ALL=C "$GNOME_EXTENSIONS_BIN" list 2>/dev/null)"
    listed_exit=$?
    enabled_output="$(LC_ALL=C "$GNOME_EXTENSIONS_BIN" list --enabled 2>/dev/null)"
    enabled_exit=$?
    set -e
    if [[ $listed_exit -eq 0 ]]; then
        listed_result="success"
        listed_uuid="$(contains_uuid "$listed_output" "$UUID")"
        listed_legacy_uuid="$(contains_uuid "$listed_output" "$LEGACY_UUID")"
    else
        listed_result="error"
    fi
    if [[ $enabled_exit -eq 0 ]]; then
        enabled_list_result="success"
        enabled_uuid="$(contains_uuid "$enabled_output" "$UUID")"
        enabled_legacy_uuid="$(contains_uuid "$enabled_output" "$LEGACY_UUID")"
    else
        enabled_list_result="error"
    fi
fi

disable_user_extensions="unavailable"
enabled_setting_result="unavailable"
enabled_setting_uuid="unknown"
enabled_setting_legacy_uuid="unknown"
if [[ "$gsettings_command_state" == "available" ]]; then
    set +e
    disable_output="$(LC_ALL=C "$GSETTINGS_BIN" get org.gnome.shell disable-user-extensions 2>/dev/null)"
    disable_exit=$?
    enabled_setting_output="$(LC_ALL=C "$GSETTINGS_BIN" get org.gnome.shell enabled-extensions 2>/dev/null)"
    enabled_setting_exit=$?
    set -e
    if [[ $disable_exit -eq 0 && "$disable_output" =~ ^(true|false)$ ]]; then
        disable_user_extensions="$disable_output"
    fi
    if [[ $enabled_setting_exit -eq 0 ]]; then
        enabled_setting_result="success"
        enabled_setting_uuid="$(setting_contains_uuid "$enabled_setting_output" "$UUID")"
        enabled_setting_legacy_uuid="$(setting_contains_uuid "$enabled_setting_output" "$LEGACY_UUID")"
    else
        enabled_setting_result="error"
    fi
fi

cat <<EOF
COPYPASTEBIN_FIRST_ACTIVATION_DIAGNOSTIC=1
capture_phase=after-login-before-launcher
session.desktop=$(safe_environment_value "${XDG_CURRENT_DESKTOP:-unknown}")
session.type=$(safe_environment_value "${XDG_SESSION_TYPE:-unknown}")
gnome.shell=$shell_version
extension.directory=$extension_directory
command.gnome_extensions=$extensions_command_state
command.gsettings=$gsettings_command_state
gnome.info.result=$info_result
gnome.info.state=$info_state
gnome.list.result=$listed_result
gnome.list.contains_public_uuid=$listed_uuid
gnome.list.contains_legacy_uuid=$listed_legacy_uuid
gnome.enabled_list.result=$enabled_list_result
gnome.enabled_list.contains_public_uuid=$enabled_uuid
gnome.enabled_list.contains_legacy_uuid=$enabled_legacy_uuid
gsettings.disable_user_extensions=$disable_user_extensions
gsettings.enabled_extensions.result=$enabled_setting_result
gsettings.enabled_extensions.contains_public_uuid=$enabled_setting_uuid
gsettings.enabled_extensions.contains_legacy_uuid=$enabled_setting_legacy_uuid
report.contains_clipboard_or_private_cpb_data=false
report.changed_system_state=false
EOF
