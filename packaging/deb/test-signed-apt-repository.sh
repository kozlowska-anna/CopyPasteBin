#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

usage() {
    printf 'Usage: %s OLD_DEB NEW_DEB\n' "${0##*/}" >&2
    exit 2
}

[[ $# -eq 2 ]] || usage

readonly OLD_DEB="$1"
readonly NEW_DEB="$2"
readonly APT_FTPARCHIVE="${CPB_APT_FTPARCHIVE:-$(command -v apt-ftparchive || true)}"
readonly WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/copypastebin-apt-test.XXXXXX")"
readonly REPOSITORY="$WORK_DIR/repository"
readonly CLIENT="$WORK_DIR/client"
readonly GNUPGHOME="$WORK_DIR/gnupg"
export GNUPGHOME

cleanup() {
    if [[ "${CPB_APT_TEST_KEEP:-0}" == "1" ]]; then
        printf 'Preserved local APT test: %s\n' "$WORK_DIR"
        return
    fi
    chmod -R u+w -- "$WORK_DIR" 2>/dev/null || true
    rm -rf -- "$WORK_DIR"
}
trap cleanup EXIT

for executable in apt-cache apt-get dpkg-deb gpg gzip; do
    command -v "$executable" >/dev/null 2>&1 || {
        printf 'Missing signed-repository test tool: %s\n' "$executable" >&2
        exit 1
    }
done
[[ -n "$APT_FTPARCHIVE" && -x "$APT_FTPARCHIVE" ]] || {
    printf 'Missing apt-ftparchive. Install apt-utils or set CPB_APT_FTPARCHIVE.\n' >&2
    exit 1
}

for package in "$OLD_DEB" "$NEW_DEB"; do
    [[ -f "$package" && ! -L "$package" ]] || {
        printf 'Expected a regular DEB file: %s\n' "$package" >&2
        exit 1
    }
    [[ "$(dpkg-deb --field "$package" Package)" == "copypastebin" ]] || {
        printf 'Unexpected package name: %s\n' "$package" >&2
        exit 1
    }
    [[ "$(dpkg-deb --field "$package" Architecture)" == "all" ]] || {
        printf 'Unexpected package architecture: %s\n' "$package" >&2
        exit 1
    }
done

readonly OLD_VERSION="$(dpkg-deb --field "$OLD_DEB" Version)"
readonly NEW_VERSION="$(dpkg-deb --field "$NEW_DEB" Version)"
dpkg --compare-versions "$NEW_VERSION" gt "$OLD_VERSION" || {
    printf 'New version %s is not newer than %s.\n' "$NEW_VERSION" "$OLD_VERSION" >&2
    exit 1
}

mkdir -p \
    "$REPOSITORY/pool/main/c/copypastebin" \
    "$REPOSITORY/dists/cpb-test/main/binary-all" \
    "$CLIENT/lists/partial" \
    "$CLIENT/cache/archives/partial" \
    "$GNUPGHOME"
chmod 0700 "$GNUPGHOME"
install -m 0444 "$OLD_DEB" "$REPOSITORY/pool/main/c/copypastebin/"
install -m 0444 "$NEW_DEB" "$REPOSITORY/pool/main/c/copypastebin/"

(
    cd "$REPOSITORY"
    "$APT_FTPARCHIVE" packages pool/main \
        >dists/cpb-test/main/binary-all/Packages
    gzip -n -c dists/cpb-test/main/binary-all/Packages \
        >dists/cpb-test/main/binary-all/Packages.gz
    "$APT_FTPARCHIVE" \
        -o APT::FTPArchive::Release::Origin=CopyPasteBin \
        -o APT::FTPArchive::Release::Label=CopyPasteBin \
        -o APT::FTPArchive::Release::Suite=cpb-test \
        -o APT::FTPArchive::Release::Codename=cpb-test \
        -o APT::FTPArchive::Release::Architectures=all \
        -o APT::FTPArchive::Release::Components=main \
        -o APT::FTPArchive::Release::Description='CopyPasteBin local signed APT test' \
        release dists/cpb-test \
        >dists/cpb-test/Release
)

readonly TEST_KEY_IDENTITY='CopyPasteBin disposable APT test key'
gpg --batch --quiet --passphrase '' \
    --quick-generate-key "$TEST_KEY_IDENTITY" ed25519 sign 1d
gpg --batch --quiet --export "$TEST_KEY_IDENTITY" \
    >"$WORK_DIR/copypastebin-test-keyring.gpg"
gpg --batch --quiet --yes --pinentry-mode loopback --passphrase '' \
    --clearsign \
    --output "$REPOSITORY/dists/cpb-test/InRelease" \
    "$REPOSITORY/dists/cpb-test/Release"
gpg --batch --quiet --yes --pinentry-mode loopback --passphrase '' \
    --armor --detach-sign \
    --output "$REPOSITORY/dists/cpb-test/Release.gpg" \
    "$REPOSITORY/dists/cpb-test/Release"

printf '%s\n' \
    "deb [arch=all signed-by=$WORK_DIR/copypastebin-test-keyring.gpg] file:$REPOSITORY cpb-test main" \
    >"$CLIENT/copypastebin.list"
printf '%s\n' \
    'Package: copypastebin' \
    'Status: install ok installed' \
    'Priority: optional' \
    'Section: utils' \
    'Architecture: all' \
    "Version: $OLD_VERSION" \
    'Description: synthetic installed package record for local APT testing' \
    >"$CLIENT/status"

readonly APT_OPTIONS=(
    -o "Dir::Etc::sourcelist=$CLIENT/copypastebin.list"
    -o 'Dir::Etc::sourceparts=-'
    -o "Dir::State::status=$CLIENT/status"
    -o "Dir::State::lists=$CLIENT/lists"
    -o "Dir::Cache=$CLIENT/cache"
    -o "Dir::Cache::archives=$CLIENT/cache/archives"
    -o 'APT::Get::List-Cleanup=0'
    -o 'Acquire::Languages=none'
    -o 'Debug::NoLocking=1'
    -o "APT::Sandbox::User=$(id -un)"
)

apt-get "${APT_OPTIONS[@]}" update >"$WORK_DIR/apt-update.log"
apt-cache "${APT_OPTIONS[@]}" policy copypastebin >"$WORK_DIR/policy.txt"

readonly INSTALLED_VERSION="$(sed -n 's/^[[:space:]]*Installed: //p' "$WORK_DIR/policy.txt")"
readonly CANDIDATE_VERSION="$(sed -n 's/^[[:space:]]*Candidate: //p' "$WORK_DIR/policy.txt")"
[[ "$INSTALLED_VERSION" == "$OLD_VERSION" ]] || {
    printf 'APT reported unexpected installed version: %s\n' "$INSTALLED_VERSION" >&2
    exit 1
}
[[ "$CANDIDATE_VERSION" == "$NEW_VERSION" ]] || {
    printf 'APT reported unexpected candidate version: %s\n' "$CANDIDATE_VERSION" >&2
    exit 1
}

readonly TAMPERED_REPOSITORY="$WORK_DIR/tampered-repository"
readonly TAMPERED_CLIENT="$WORK_DIR/tampered-client"
cp -a "$REPOSITORY" "$TAMPERED_REPOSITORY"
rm -- "$TAMPERED_REPOSITORY/dists/cpb-test/InRelease"
printf '\nDescription: deliberately tampered local test\n' \
    >>"$TAMPERED_REPOSITORY/dists/cpb-test/Release"
mkdir -p \
    "$TAMPERED_CLIENT/lists/partial" \
    "$TAMPERED_CLIENT/cache/archives/partial"
printf '%s\n' \
    "deb [arch=all signed-by=$WORK_DIR/copypastebin-test-keyring.gpg] file:$TAMPERED_REPOSITORY cpb-test main" \
    >"$TAMPERED_CLIENT/copypastebin.list"

readonly TAMPERED_APT_OPTIONS=(
    -o "Dir::Etc::sourcelist=$TAMPERED_CLIENT/copypastebin.list"
    -o 'Dir::Etc::sourceparts=-'
    -o "Dir::State::status=$CLIENT/status"
    -o "Dir::State::lists=$TAMPERED_CLIENT/lists"
    -o "Dir::Cache=$TAMPERED_CLIENT/cache"
    -o "Dir::Cache::archives=$TAMPERED_CLIENT/cache/archives"
    -o 'APT::Get::List-Cleanup=0'
    -o 'Acquire::Languages=none'
    -o 'Debug::NoLocking=1'
    -o "APT::Sandbox::User=$(id -un)"
)
if apt-get "${TAMPERED_APT_OPTIONS[@]}" update \
    >"$WORK_DIR/tampered-apt-update.log" 2>&1; then
    printf 'APT accepted repository metadata with an invalid signature.\n' >&2
    exit 1
fi

printf 'signed repository verification: PASS\n'
printf 'tampered repository rejection: PASS\n'
printf 'installed=%s\n' "$INSTALLED_VERSION"
printf 'candidate=%s\n' "$CANDIDATE_VERSION"
