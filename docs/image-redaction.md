# Image redaction in CopyPasteBin 1.1

**English** | [Polski](image-redaction.pl.md)

This document describes the image editor available in CopyPasteBin 1.1.

## User flow

1. Choose **Anonymize image** from the CopyPasteBin menu.
2. Open a local PNG or JPEG file.
3. Drag a rectangle over each sensitive area. Each rectangle is previewed with
   the same opaque color that will replace its pixels.
4. If needed, undo the last rectangle.
5. Save a new PNG file.

The original is never modified. The editor also refuses to replace any other
existing destination. A successful output is a newly encoded PNG with no
metadata copied from the source.

## Technical boundary

The image editor is a separate on-demand GJS/GTK 4 process. It imports the
platform's existing GdkPixbuf library, so the release adds no Python package
or network dependency. It has no stdin pipe to the extension and does not use
the text detection engine, clipboard API, screenshot API, network, or a
temporary image file.

The module accepts only local regular files, rejects symlinks, and limits the
compressed file size, dimensions, and total pixel count before full decoding.
Selected rectangles are stored only in the open process. Saving copies the
decoded pixel buffer, replaces every selected rectangle with opaque pixels,
encodes a fresh PNG in memory, and exclusively creates a private destination
file.

## Explicitly out of scope

- OCR or automatic detection;
- screenshot capture or directory monitoring;
- image clipboard monitoring;
- freehand drawing, blur, pixelation, or a general-purpose image editor;
- network services, telemetry, and administrator privileges.

## Verification

Automated tests use only generated PNG and JPEG fixtures in temporary
directories. The release scope covers opening the editor from the menu,
loading a synthetic image, drawing and undoing a rectangle, and saving a new
PNG in the target GNOME Shell 50/Wayland environment.
