# Installing CopyPasteBin 1.1

CopyPasteBin 1.1 has two installers from the same source set:

- [Debian package `copypastebin_1.1-1_all.deb`](https://github.com/kozlowska-anna/CopyPasteBin/releases/download/v1.1/copypastebin_1.1-1_all.deb) for a system installation managed by APT;
- [archive `CopyPasteBin-linux-1.1.tar.gz`](https://github.com/kozlowska-anna/CopyPasteBin/releases/download/v1.1/CopyPasteBin-linux-1.1.tar.gz) for a user-local installation.

Also download [`SHA256SUMS`](https://github.com/kozlowska-anna/CopyPasteBin/releases/download/v1.1/SHA256SUMS) and verify the selected file before opening it. Do not install both variants at the same time.

The supported scope is GNOME Shell 50 on Wayland with Python 3.11 or newer.
KDE Plasma, Cinnamon, and Xfce integration has not been verified. There is no
CopyPasteBin APT repository, so a locally downloaded DEB does not receive
automatic updates.

## User-local tar.gz

Open a terminal in the download directory and verify the archive before
extracting it:

```sh
sha256sum --check --ignore-missing SHA256SUMS
```

Continue only if the command reports:

```text
CopyPasteBin-linux-1.1.tar.gz: OK
```

Extract the verified archive and enter its directory:

```sh
tar -xzf CopyPasteBin-linux-1.1.tar.gz
cd CopyPasteBin-linux-1.1
```

## Check compatibility and install

After extracting the package, open a terminal in its folder. For example, use
the **Open in Terminal** option in the file manager's context menu. Then run the
read-only compatibility check:

```sh
./install.sh --check-only
```

This command does not install or modify CopyPasteBin. If the compatibility
check succeeds, install the application for the current user:

```sh
./install.sh
```

The installer does not require `sudo`, a package manager, or network access.
Log out and log back in to the GNOME Wayland session. CopyPasteBin should then
start automatically.

## Package contents

The package contains:

- the local Python core as a wheel with no network dependencies;
- the complete `copypastebin@kozlowska-anna.github.io` extension;
- the locally compiled GSettings schema for the `Super+Shift+V` shortcut;
- the launcher, scalable application icon, and hidden icon mappings for six
  GTK windows;
- the on-demand image editor for local PNG and JPEG files, saving redacted
  output as a new PNG;
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

Version 1.1 supports GNOME Shell 50 on Wayland with Python 3.11 or newer,
including `venv`, GJS, GTK 4, GioUnix, GNOME Extensions, and `sha256sum`.
Cinnamon, KDE Plasma, and Xfce desktop integrations are not supported in this
release. The installer stops safely when GNOME Shell is unavailable.

## Debian package

Verify the checksum and inspect the downloaded package:

```sh
sha256sum copypastebin_1.1-1_all.deb
dpkg-deb --info copypastebin_1.1-1_all.deb
```

Install it after explicitly approving administrative access:

```sh
sudo apt install ./copypastebin_1.1-1_all.deb
```

The package does not start CopyPasteBin as root, has no maintainer scripts,
and does not enable the extension during installation. Log out and back in to
GNOME Wayland, then choose **Enable CopyPasteBin** from the application menu.
Use the same APT command with a newer local file to update. Ubuntu Software
did not upgrade an existing local DEB during testing, so APT is the documented
manual update method.

Remove package-owned code with:

```sh
sudo apt remove copypastebin
```

Removal preserves `~/.config/copypastebin` and
`~/.local/state/copypastebin`. A graphical installer may describe the local,
unsigned DEB as coming from an unknown publisher or having unrestricted
permissions. Package metadata cannot honestly remove those warnings without a
signed repository or sandbox.

## Changing installation method

For tar.gz to DEB, first run `./uninstall.sh` from the current archive, then
install the DEB. This preserves private state while removing the user-local
backend, launchers, and same-UUID extension that would otherwise take
precedence over the system extension. The DEB activation helper refuses to
proceed while that conflict exists; it never removes user files automatically.

For DEB to tar.gz, first remove the DEB with `apt remove`, then run
`./install.sh` from the archive. Do not keep both installation methods active
at the same time. Reinstalling the same version does not remove private state.

## If CopyPasteBin does not start automatically

This troubleshooting step is not part of a normal installation. Use it only if
CopyPasteBin does not appear after logging back in. Before starting
CopyPasteBin manually, run the included read-only diagnostic from the extracted
package directory:

```sh
./diagnose-first-activation.sh
```

The diagnostic reports only bounded technical information about the GNOME
session and the CopyPasteBin extension. It does not print clipboard content,
CopyPasteBin private data, the home-directory path, or names of unrelated
extensions, and it changes nothing.
