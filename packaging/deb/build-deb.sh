#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

readonly ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)"
readonly VERSION="$(dpkg-parsechangelog -l "$ROOT/debian/changelog" -S Version)"
readonly SOURCE_DATE_EPOCH="$(dpkg-parsechangelog -l "$ROOT/debian/changelog" -S Timestamp)"
readonly DIST_DIR="${CPB_DEB_DIST_DIR:-$ROOT/dist}"
readonly WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/copypastebin-deb.XXXXXX")"
readonly SOURCE_DIR="$WORK_DIR/source"
readonly PACKAGES=(
    "copypastebin-backend"
    "gnome-shell-extension-copypastebin"
    "copypastebin"
)
export SOURCE_DATE_EPOCH

[[ "$DIST_DIR" = /* && "$DIST_DIR" != "/" ]] || {
    printf 'Artifact directory must be an absolute, narrow path.\n' >&2
    exit 2
}

cleanup() {
    chmod -R u+w -- "$WORK_DIR" 2>/dev/null || true
    rm -rf -- "$WORK_DIR"
}
trap cleanup EXIT

for executable in dpkg-buildpackage dpkg-deb dpkg-parsechangelog dh; do
    command -v "$executable" >/dev/null 2>&1 || {
        printf 'Missing Debian package build tool: %s\n' "$executable" >&2
        exit 1
    }
done

mkdir -p -- "$SOURCE_DIR" "$DIST_DIR"
for source_path in debian packaging gnome-extension src LICENSE NOTICE; do
    cp -a -- "$ROOT/$source_path" "$SOURCE_DIR/"
done

(
    cd -- "$SOURCE_DIR"
    dpkg-buildpackage --build=binary --no-sign >/dev/null
)

for package in "${PACKAGES[@]}"; do
    candidate="$WORK_DIR/${package}_${VERSION}_all.deb"
    output="$DIST_DIR/${package}_${VERSION}_all.deb"
    [[ -f "$candidate" && ! -L "$candidate" ]] || {
        printf 'Expected binary package was not built: %s\n' "$candidate" >&2
        exit 1
    }
    [[ "$(dpkg-deb --field "$candidate" Package)" == "$package" ]] || {
        printf 'Built package has an unexpected name: %s\n' "$candidate" >&2
        exit 1
    }
    [[ "$(dpkg-deb --field "$candidate" Version)" == "$VERSION" ]] || {
        printf 'Built package has an unexpected version: %s\n' "$candidate" >&2
        exit 1
    }
    if [[ -e "$output" ]]; then
        [[ -f "$output" && ! -L "$output" ]] || {
            printf 'Refusing to replace invalid artifact: %s\n' "$output" >&2
            exit 1
        }
        cmp -s -- "$candidate" "$output" || {
            printf 'Artifact %s exists and differs from the new build. Bump the version.\n' \
                "$output" >&2
            exit 1
        }
    else
        install -m 0444 -- "$candidate" "$output"
    fi
    printf '%s\n' "$output"
done
