#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

readonly ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
readonly CHANNEL="${CPB_BUNDLE_CHANNEL:-release}"
case "$CHANNEL" in
    release)
        VERSION="1.2"
        PYTHON_PROJECT_VERSION="1.2"
        EXTENSION_VERSION="7"
        ;;
    development)
        VERSION="1.3-dev"
        PYTHON_PROJECT_VERSION="1.3.dev0"
        EXTENSION_VERSION="8"
        ;;
    *)
        printf 'Nieobsługiwany kanał budowy: %s\n' "$CHANNEL" >&2
        exit 2
        ;;
esac
readonly VERSION PYTHON_PROJECT_VERSION EXTENSION_VERSION
readonly SOURCE_DATE_EPOCH="1793491200"
readonly UUID="copypastebin@kozlowska-anna.github.io"
readonly WINDOW_APPLICATION_IDS=(
    "io.github.copypastebin.Editor"
    "io.github.copypastebin.ImageRedactor"
    "io.github.copypastebin.FilterEditor"
    "io.github.copypastebin.RulesEditor"
    "io.github.copypastebin.RecentClipboard"
    "io.github.copypastebin.About"
)
readonly BUNDLE_NAME="CopyPasteBin-linux-$VERSION"
readonly DIST_DIR="${CPB_BUNDLE_DIST_DIR:-$ROOT/dist}"
readonly WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/copypastebin-bundle.XXXXXX")"
readonly BUILD_SOURCE_DIR="$WORK_DIR/source"
readonly STAGE_DIR="$WORK_DIR/$BUNDLE_NAME"
readonly PAYLOAD_DIR="$STAGE_DIR/payload"
readonly PYTHON_BIN="${PYTHON_BIN:-python3}"

[[ "$DIST_DIR" = /* && "$DIST_DIR" != "/" ]] || {
    printf 'Katalog artefaktów musi być bezwzględną, zawężoną ścieżką.\n' >&2
    exit 2
}

cleanup() {
    chmod -R u+w -- "$WORK_DIR" 2>/dev/null || true
    rm -rf -- "$WORK_DIR"
}
trap cleanup EXIT

"$PYTHON_BIN" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY

mkdir -p -- "$BUILD_SOURCE_DIR/src" "$PAYLOAD_DIR" "$DIST_DIR"
export SOURCE_DATE_EPOCH

cp -- "$ROOT/pyproject.toml" "$ROOT/LICENSE" "$ROOT/NOTICE" \
    "$BUILD_SOURCE_DIR/"
cp -a -- "$ROOT/src/." "$BUILD_SOURCE_DIR/src/"
if [[ "$CHANNEL" == "development" ]]; then
    "$PYTHON_BIN" - \
        "$BUILD_SOURCE_DIR/pyproject.toml" \
        "$BUILD_SOURCE_DIR/src/copypastebin/__init__.py" \
        "$PYTHON_PROJECT_VERSION" <<'PY'
from pathlib import Path
import sys

pyproject = Path(sys.argv[1])
package_init = Path(sys.argv[2])
version = sys.argv[3]

for path, old, new in (
    (pyproject, 'version = "1.2"', f'version = "{version}"'),
    (package_init, '__version__ = "1.2"', f'__version__ = "{version}"'),
):
    source = path.read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise SystemExit(f"unexpected version marker in {path}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
PY
fi
find "$BUILD_SOURCE_DIR" -type d -exec chmod 0755 -- {} +
find "$BUILD_SOURCE_DIR" -type f -exec chmod 0644 -- {} +

"$PYTHON_BIN" -m pip wheel --no-deps --no-build-isolation \
    --wheel-dir "$PAYLOAD_DIR" "$BUILD_SOURCE_DIR" >/dev/null

cp -a -- "$ROOT/gnome-extension/$UUID" "$PAYLOAD_DIR/"
if [[ "$CHANNEL" == "development" ]]; then
    "$PYTHON_BIN" - \
        "$PAYLOAD_DIR/$UUID/about.js" \
        "$PAYLOAD_DIR/$UUID/metadata.json" \
        "$VERSION" "$EXTENSION_VERSION" <<'PY'
from pathlib import Path
import json
import sys

about_path = Path(sys.argv[1])
metadata_path = Path(sys.argv[2])
display_version = sys.argv[3]
extension_version = int(sys.argv[4])

about = about_path.read_text(encoding="utf-8")
old = "const VERSION = '1.2';"
if about.count(old) != 1:
    raise SystemExit("unexpected About version marker")
about_path.write_text(
    about.replace(old, f"const VERSION = '{display_version}';", 1),
    encoding="utf-8",
)

metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
if metadata.get("version") != 7:
    raise SystemExit("unexpected extension version marker")
metadata["version"] = extension_version
metadata_path.write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
fi
cp -- "$ROOT/packaging/copypastebin.desktop" "$PAYLOAD_DIR/copypastebin.desktop"
cp -- "$ROOT/packaging/persist-extension-enablement.js" \
    "$PAYLOAD_DIR/persist-extension-enablement.js"
for application_id in "${WINDOW_APPLICATION_IDS[@]}"; do
    cp -- "$ROOT/packaging/copypastebin-window.desktop" \
        "$PAYLOAD_DIR/$application_id.desktop"
done
cp -- "$ROOT/packaging/copypastebin-app.svg" "$PAYLOAD_DIR/copypastebin.svg"
cp -- "$ROOT/packaging/offline/install.sh" "$STAGE_DIR/install.sh"
cp -- "$ROOT/packaging/offline/uninstall.sh" "$STAGE_DIR/uninstall.sh"
cp -- "$ROOT/packaging/offline/refresh-user-icon-cache.sh" \
    "$STAGE_DIR/refresh-user-icon-cache.sh"
cp -- "$ROOT/packaging/offline/diagnose-first-activation.sh" \
    "$STAGE_DIR/diagnose-first-activation.sh"
for document in README.md README.pl.md INSTALL.md INSTALL.pl.md; do
    cp -- "$ROOT/packaging/offline/$document" "$STAGE_DIR/$document"
done
# Preserve the full security model, adapting only the language-switch paths.
sed -e 's|(docs/security.pl.md)|(SECURITY.pl.md)|g' -e 's|(docs/image-redaction.md)|(IMAGE-REDACTION.md)|g' "$ROOT/SECURITY.md" > "$STAGE_DIR/SECURITY.md"
sed -e 's|(../SECURITY.md)|(SECURITY.md)|g' -e 's|(image-redaction.pl.md)|(IMAGE-REDACTION.pl.md)|g' "$ROOT/docs/security.pl.md" > "$STAGE_DIR/SECURITY.pl.md"
sed 's|(image-redaction.pl.md)|(IMAGE-REDACTION.pl.md)|g' "$ROOT/docs/image-redaction.md" > "$STAGE_DIR/IMAGE-REDACTION.md"
sed 's|(image-redaction.md)|(IMAGE-REDACTION.md)|g' "$ROOT/docs/image-redaction.pl.md" > "$STAGE_DIR/IMAGE-REDACTION.pl.md"
cp -- "$ROOT/LICENSE" "$STAGE_DIR/LICENSE"
cp -- "$ROOT/NOTICE" "$STAGE_DIR/NOTICE"
chmod 0755 -- "$STAGE_DIR/install.sh" "$STAGE_DIR/uninstall.sh" \
    "$STAGE_DIR/refresh-user-icon-cache.sh" \
    "$STAGE_DIR/diagnose-first-activation.sh"
find "$STAGE_DIR" -type d -exec chmod 0755 -- {} +
find "$STAGE_DIR" -type f -exec chmod 0444 -- {} +
chmod 0555 -- "$STAGE_DIR/install.sh" "$STAGE_DIR/uninstall.sh" \
    "$STAGE_DIR/refresh-user-icon-cache.sh" \
    "$STAGE_DIR/diagnose-first-activation.sh"

(
    cd -- "$STAGE_DIR"
    find payload -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
)
chmod 0444 -- "$STAGE_DIR/SHA256SUMS"
find "$STAGE_DIR" -type d -exec chmod 0555 -- {} +

archive_name="$BUNDLE_NAME.tar.gz"
archive="$DIST_DIR/$archive_name"
candidate_archive="$WORK_DIR/$archive_name"
tar --sort=name --format=posix --pax-option=delete=atime,delete=ctime \
    --mtime="@$SOURCE_DATE_EPOCH" --owner=0 --group=0 --numeric-owner \
    -C "$WORK_DIR" -czf "$candidate_archive" "$BUNDLE_NAME"
if [[ -e "$archive" ]]; then
    [[ -f "$archive" && ! -L "$archive" ]] || {
        printf 'Odmowa zastąpienia nieprawidłowego artefaktu: %s\n' "$archive" >&2
        exit 1
    }
    cmp -s -- "$candidate_archive" "$archive" || {
        printf 'Artefakt %s już istnieje i różni się od nowej budowy. Zmień wersję zamiast go nadpisywać.\n' \
            "$archive" >&2
        exit 1
    }
else
    install -m 0444 -- "$candidate_archive" "$archive"
fi
chmod 0444 -- "$archive"
checksum_tmp="$DIST_DIR/.SHA256SUMS.tmp.$$"
(
    cd -- "$DIST_DIR"
    sha256sum "$archive_name"
) > "$checksum_tmp"
chmod 0444 -- "$checksum_tmp"
mv -f -- "$checksum_tmp" "$DIST_DIR/SHA256SUMS"
archive_checksum_tmp="$DIST_DIR/.$archive_name.sha256.tmp.$$"
cp -- "$DIST_DIR/SHA256SUMS" "$archive_checksum_tmp"
chmod 0444 -- "$archive_checksum_tmp"
mv -f -- "$archive_checksum_tmp" "$archive.sha256"

printf '%s\n' "$archive"
