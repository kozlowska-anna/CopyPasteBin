#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

readonly ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)"
readonly PACKAGE="copypastebin"
readonly UPSTREAM_VERSION="1.2.1"
readonly SOURCE_REF="${CPB_DEB_SOURCE_REF:-HEAD}"
readonly DIST_DIR="${CPB_DEB_SOURCE_DIST_DIR:-$ROOT/dist/source}"
readonly WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/copypastebin-source.XXXXXX")"
readonly SOURCE_DIR="$WORK_DIR/${PACKAGE}-${UPSTREAM_VERSION}"
readonly UPSTREAM_EXPORT="$WORK_DIR/upstream"
readonly UPSTREAM_DIR="$UPSTREAM_EXPORT/${PACKAGE}-${UPSTREAM_VERSION}"

[[ "$DIST_DIR" = /* && "$DIST_DIR" != "/" ]] || {
    printf 'Source artifact directory must be an absolute, narrow path.\n' >&2
    exit 2
}

cleanup() {
    chmod -R u+w -- "$WORK_DIR" 2>/dev/null || true
    rm -rf -- "$WORK_DIR"
}
trap cleanup EXIT

for executable in git dpkg-parsechangelog dpkg-source gzip tar; do
    command -v "$executable" >/dev/null 2>&1 || {
        printf 'Missing source-package build tool: %s\n' "$executable" >&2
        exit 1
    }
done

git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    printf 'The source-package builder requires a Git checkout.\n' >&2
    exit 1
}

readonly RESOLVED_REF="$(git -C "$ROOT" rev-parse --verify "${SOURCE_REF}^{commit}")"
readonly SOURCE_DATE_EPOCH="$(git -C "$ROOT" show -s --format=%ct "$RESOLVED_REF")"
readonly DEBIAN_VERSION="$(dpkg-parsechangelog -l "$ROOT/debian/changelog" -S Version)"
export SOURCE_DATE_EPOCH

case "$DEBIAN_VERSION" in
    "$UPSTREAM_VERSION"-*) ;;
    *)
        printf 'Debian version %s does not match upstream version %s.\n' \
            "$DEBIAN_VERSION" "$UPSTREAM_VERSION" >&2
        exit 1
        ;;
esac

for generated_path in \
    "$ROOT/debian/.debhelper" \
    "$ROOT/debian/$PACKAGE" \
    "$ROOT/debian/copypastebin-backend" \
    "$ROOT/debian/gnome-shell-extension-copypastebin" \
    "$ROOT/debian/debhelper-build-stamp" \
    "$ROOT/debian/files" \
    "$ROOT/debian/${PACKAGE}.debhelper.log" \
    "$ROOT/debian/${PACKAGE}.substvars"; do
    if [[ -e "$generated_path" ]]; then
        printf 'Refusing to include generated Debian build state: %s\n' \
            "$generated_path" >&2
        exit 1
    fi
done

mkdir -p -- "$SOURCE_DIR" "$UPSTREAM_EXPORT" "$DIST_DIR"
git -C "$ROOT" archive --format=tar \
    --prefix="${PACKAGE}-${UPSTREAM_VERSION}/" "$RESOLVED_REF" \
    | tar -xf - -C "$UPSTREAM_EXPORT"
rm -rf -- "$UPSTREAM_DIR/debian"
cp -a -- "$UPSTREAM_DIR/." "$SOURCE_DIR/"
cp -a -- "$ROOT/debian" "$SOURCE_DIR/debian"
find "$SOURCE_DIR/debian" -type d -exec chmod 0755 -- {} +
find "$SOURCE_DIR/debian" -type f -exec chmod 0644 -- {} +
chmod 0755 -- \
    "$SOURCE_DIR/debian/refresh-user-icon-cache" \
    "$SOURCE_DIR/debian/rules" \
    "$SOURCE_DIR/debian/tests/backend-only" \
    "$SOURCE_DIR/debian/tests/smoke"
find "$SOURCE_DIR/debian" -exec touch -h -d "@$SOURCE_DATE_EPOCH" -- {} +

readonly ORIG_TARBALL="$WORK_DIR/${PACKAGE}_${UPSTREAM_VERSION}.orig.tar.gz"
tar --sort=name --format=gnu --mtime="@$SOURCE_DATE_EPOCH" \
    --owner=0 --group=0 --numeric-owner \
    -C "$UPSTREAM_EXPORT" -cf - "${PACKAGE}-${UPSTREAM_VERSION}" \
    | gzip -n >"$ORIG_TARBALL"

(
    cd -- "$SOURCE_DIR"
    dpkg-source -b .
)

readonly ARTIFACTS=(
    "$ORIG_TARBALL"
    "$WORK_DIR/${PACKAGE}_${DEBIAN_VERSION}.debian.tar.xz"
    "$WORK_DIR/${PACKAGE}_${DEBIAN_VERSION}.dsc"
)

for artifact in "${ARTIFACTS[@]}"; do
    destination="$DIST_DIR/$(basename -- "$artifact")"
    if [[ -e "$destination" ]]; then
        [[ -f "$destination" && ! -L "$destination" ]] || {
            printf 'Refusing to replace invalid artifact: %s\n' "$destination" >&2
            exit 1
        }
        cmp -s -- "$artifact" "$destination" || {
            printf 'Artifact %s exists and differs from the new build. Bump the version.\n' \
                "$destination" >&2
            exit 1
        }
    else
        install -m 0444 -- "$artifact" "$destination"
    fi
    printf '%s\n' "$destination"
done
