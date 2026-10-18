# Offline installation on another computer

The `CopyPasteBin-offline-linux-1.0.0.tar.gz` package provides a controlled,
local installation of CopyPasteBin 1.0.0. The confirmed supported environment
is GNOME Shell 50 on Wayland with Python 3.11 or newer.

## Download CopyPasteBin 1.0.0

### [Download CopyPasteBin 1.0.0](https://github.com/kozlowska-anna/CopyPasteBin/releases/download/v1.0.0/CopyPasteBin-offline-linux-1.0.0.tar.gz)

[Download the SHA-256 checksum](https://github.com/kozlowska-anna/CopyPasteBin/releases/download/v1.0.0/CopyPasteBin-offline-linux-1.0.0.tar.gz.sha256)

Download both files into the same directory. The expected SHA-256 of the
archive is:

```text
5146736df8eb04bf2d5e477d48d1b02a984a490f486915d283e71bc71d7bbb6b
```

## Verify and extract the download

Open a terminal in the download directory and verify the archive before
extracting it:

```sh
sha256sum --check CopyPasteBin-offline-linux-1.0.0.tar.gz.sha256
```

Continue only if the command reports:

```text
CopyPasteBin-offline-linux-1.0.0.tar.gz: OK
```

Extract the verified archive and enter its directory:

```sh
tar -xzf CopyPasteBin-offline-linux-1.0.0.tar.gz
cd CopyPasteBin-offline-linux-1.0.0
```

## Check compatibility and install

Run the read-only compatibility check first:

```sh
./install.sh --check-only
```

This command does not install or modify CopyPasteBin. If it reports
`Kontrola zgodności: OK`, install the application for the current user:

```sh
./install.sh
```

The installer does not require `sudo`, a package manager, or network access.
Log out and log back in to the GNOME Wayland session. CopyPasteBin should then
start automatically.

If it does not appear after the first login, run the included read-only
diagnostic before starting CopyPasteBin manually:

```sh
./diagnose-first-activation.sh
```

The diagnostic reports only bounded technical information about the GNOME
session and the CopyPasteBin extension. It does not print clipboard content,
CopyPasteBin private data, the home-directory path, or names of unrelated
extensions, and it changes nothing.

## Package contents

The package contains:

- the local Python core as a wheel with no network dependencies;
- the complete `copypastebin@kozlowska-anna.github.io` extension;
- the locally compiled GSettings schema for the `Super+Shift+V` shortcut;
- the launcher, scalable application icon, and hidden icon mappings for five
  GTK windows;
- an installer with a read-only check mode;
- a conservative uninstaller that preserves settings and history;
- SHA-256 checksums for every payload file.

It does not contain configuration, history, the metadata database, an HMAC
key, clipboard content, or other data from the computer where it was built.

## Installer boundaries

The installer writes only to fixed locations for the current user under
`~/.local/share`. Before writing, it verifies package integrity, the Python
version, GNOME Shell, `venv`, `gjs`, GTK 4, and the required GObject libraries.
Symbolic links at installation targets are rejected.

An update preserves `~/.config/copypastebin` and
`~/.local/state/copypastebin`, including the selected interface language. If
creation of the new environment or copying of the extension fails, the
installer restores the previous program version.

When upgrading a development installation, the installer migrates the
extension from `copypastebin@local` to the public UUID
`copypastebin@kozlowska-anna.github.io`. It disables and removes the old code
only after successful installation of the new version. Configuration and
state remain in their existing private directories.

## Update

Download and verify the new release, extract it into a new directory, and run
its `./install.sh`. Do not uninstall the existing version first. The update
preserves the user's private configuration and history.

## Remove the installed code

Run the uninstaller from the current package:

```sh
./uninstall.sh
```

Do not use an uninstaller from an older extracted directory because an older
version may not know the public extension UUID. The current script removes the
installed code, extension, and launcher, but intentionally preserves local
settings and history.

## Supported environment

Version 1.0.0 supports GNOME Shell 50 on Wayland with Python 3.11 or newer,
including `venv`, GJS, GTK 4, GioUnix, GNOME Extensions, and `sha256sum`.
Cinnamon, KDE Plasma, and Xfce desktop integrations are not supported in this
release. The installer stops safely when GNOME Shell is unavailable.
