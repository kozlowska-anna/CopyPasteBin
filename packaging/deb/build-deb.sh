#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

readonly ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)"
readonly PACKAGE="copypastebin"
readonly VERSION="1.1-1"
readonly UUID="copypastebin@kozlowska-anna.github.io"
readonly SOURCE_DATE_EPOCH="1792454400"
readonly DIST_DIR="${CPB_DEB_DIST_DIR:-$ROOT/dist}"
readonly WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/copypastebin-deb.XXXXXX")"
readonly STAGE_DIR="$WORK_DIR/root"
readonly EXTENSION_DIR="$STAGE_DIR/usr/share/gnome-shell/extensions/$UUID"
readonly PYTHON_PACKAGE_DIR="$STAGE_DIR/usr/lib/python3/dist-packages/copypastebin"
readonly APPLICATIONS_DIR="$STAGE_DIR/usr/share/applications"
readonly METAINFO_DIR="$STAGE_DIR/usr/share/metainfo"
readonly ENABLE_HELPER_DIR="$STAGE_DIR/usr/share/copypastebin"
readonly DOC_DIR="$STAGE_DIR/usr/share/doc/$PACKAGE"
readonly WINDOW_APPLICATION_IDS=(
    "io.github.copypastebin.Editor"
    "io.github.copypastebin.ImageRedactor"
    "io.github.copypastebin.FilterEditor"
    "io.github.copypastebin.RulesEditor"
    "io.github.copypastebin.RecentClipboard"
    "io.github.copypastebin.About"
)
export SOURCE_DATE_EPOCH

cleanup() {
    chmod -R u+w -- "$WORK_DIR" 2>/dev/null || true
    rm -rf -- "$WORK_DIR"
}
trap cleanup EXIT

for executable in dpkg-deb glib-compile-schemas; do
    command -v "$executable" >/dev/null 2>&1 || {
        printf 'Brak wymaganego narzędzia budowy: %s\n' "$executable" >&2
        exit 1
    }
done

mkdir -p -- \
    "$STAGE_DIR/DEBIAN" \
    "$STAGE_DIR/usr/bin" \
    "$PYTHON_PACKAGE_DIR" \
    "$EXTENSION_DIR" \
    "$APPLICATIONS_DIR" \
    "$METAINFO_DIR" \
    "$ENABLE_HELPER_DIR" \
    "$STAGE_DIR/usr/share/icons/hicolor/scalable/apps" \
    "$DOC_DIR" \
    "$DIST_DIR"

install -m 0644 -- "$ROOT/packaging/deb/control" "$STAGE_DIR/DEBIAN/control"
install -m 0755 -- "$ROOT/packaging/deb/cpb" "$STAGE_DIR/usr/bin/cpb"
cp -a -- "$ROOT/src/copypastebin/." "$PYTHON_PACKAGE_DIR/"
find "$PYTHON_PACKAGE_DIR" -type d -name __pycache__ -prune -exec rm -rf -- {} +
find "$PYTHON_PACKAGE_DIR" -type f -name '*.py[co]' -delete

cp -a -- "$ROOT/gnome-extension/$UUID/." "$EXTENSION_DIR/"
glib-compile-schemas "$EXTENSION_DIR/schemas"

install -m 0644 -- "$ROOT/packaging/deb/copypastebin.desktop" \
    "$APPLICATIONS_DIR/copypastebin.desktop"
install -m 0644 -- "$ROOT/packaging/deb/enable-extension.js" \
    "$ENABLE_HELPER_DIR/enable-extension.js"
for application_id in "${WINDOW_APPLICATION_IDS[@]}"; do
    install -m 0644 -- "$ROOT/packaging/copypastebin-window.desktop" \
        "$APPLICATIONS_DIR/$application_id.desktop"
done
install -m 0644 -- "$ROOT/packaging/copypastebin-app.svg" \
    "$STAGE_DIR/usr/share/icons/hicolor/scalable/apps/copypastebin.svg"
install -m 0644 -- "$ROOT/packaging/deb/io.github.kozlowska_anna.CopyPasteBin.metainfo.xml" \
    "$METAINFO_DIR/io.github.kozlowska_anna.CopyPasteBin.metainfo.xml"
install -m 0644 -- "$ROOT/packaging/deb/README.Debian" "$DOC_DIR/README.Debian"
install -m 0644 -- "$ROOT/packaging/deb/copyright" "$DOC_DIR/copyright"
install -m 0644 -- "$ROOT/LICENSE" "$DOC_DIR/LICENSE"
install -m 0644 -- "$ROOT/NOTICE" "$DOC_DIR/NOTICE"

find "$STAGE_DIR" -type d -exec chmod 0755 -- {} +
find "$STAGE_DIR" -type f -exec chmod 0644 -- {} +
chmod 0755 -- "$STAGE_DIR/usr/bin/cpb"
find "$STAGE_DIR" -exec touch -h -d "@$SOURCE_DATE_EPOCH" -- {} +

readonly OUTPUT="$DIST_DIR/${PACKAGE}_${VERSION}_all.deb"
readonly CANDIDATE="$WORK_DIR/${PACKAGE}_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$STAGE_DIR" "$CANDIDATE" >/dev/null

if [[ -e "$OUTPUT" ]]; then
    [[ -f "$OUTPUT" && ! -L "$OUTPUT" ]] || {
        printf 'Odmowa zastąpienia nieprawidłowego artefaktu: %s\n' "$OUTPUT" >&2
        exit 1
    }
    cmp -s -- "$CANDIDATE" "$OUTPUT" || {
        printf 'Artefakt %s istnieje i różni się od nowej budowy. Zmień wersję.\n' \
            "$OUTPUT" >&2
        exit 1
    }
else
    install -m 0444 -- "$CANDIDATE" "$OUTPUT"
fi

printf '%s\n' "$OUTPUT"
