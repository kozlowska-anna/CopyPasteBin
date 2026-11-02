#!/usr/bin/env bash
set -Eeuo pipefail

[[ -n "${HOME:-}" && "$HOME" = /* && "$HOME" != "/" ]] || exit 0

readonly ICON_ROOT="$HOME/.local/share/icons/hicolor"
[[ -d "$ICON_ROOT" && ! -L "$ICON_ROOT" ]] || exit 0
[[ -x /usr/bin/gtk-update-icon-cache ]] || exit 0

/usr/bin/gtk-update-icon-cache --force --ignore-theme-index "$ICON_ROOT" \
    >/dev/null 2>&1 || true
