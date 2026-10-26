# Offline installation

**English** | [Polski](INSTALL.pl.md) | [Overview](README.md)

Requirements: Linux, GNOME Shell 50, Wayland, Python 3.11+ with venv,
/usr/bin/gnome-extensions, /usr/bin/gjs, GTK 4, GioUnix, and sha256sum.
KDE Plasma, Cinnamon, and Xfce are not supported.

## Install

Verify the downloaded archive using its accompanying .sha256 file before
extracting it (`sha256sum --check ARCHIVE_NAME.tar.gz.sha256`). Proceed only on OK.
Extract the archive and open a terminal in the extracted folder. Run:

```sh
./install.sh --check-only
./install.sh
```

The first command only checks compatibility; run the second only after success.
Log out and back in to GNOME Wayland.
The installer is user-local, offline, and requires no sudo. It installs code under
~/.local/share and includes no private data from the build computer.

## Upgrade

Verify and extract the new package into a new folder. Run its ./install.sh
without uninstalling first. Settings in ~/.config/copypastebin and state in
~/.local/state/copypastebin are preserved. Migration from the development UUID
copypastebin@local to copypastebin@kozlowska-anna.github.io removes the old code
only after successful installation; failure restores the previous directory.

## Uninstall

From the current extracted package, run:

```sh
./uninstall.sh
```

Use the current script, not an older version. This removes installed code while
preserving configuration and history in the private directories listed above.

## Troubleshooting

Only if the application does not start after logging back in, run this before
starting it manually from the application menu:

```sh
./diagnose-first-activation.sh
```

The report changes nothing and contains no clipboard content, history, rules,
exceptions, home-directory path, or list of other extensions. Review it before
manually attaching it to an issue. Nothing is sent automatically.

## Usage and safety

Super+Shift+V starts Safe Paste on demand; it neither pastes automatically nor
intercepts Ctrl+V. Read the [protection limitations](SECURITY.md).
