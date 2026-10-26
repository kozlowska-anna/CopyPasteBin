import Gio from 'gi://Gio';
import GdkPixbuf from 'gi://GdkPixbuf';

export const MAX_INPUT_BYTES = 100 * 1024 * 1024;
export const MAX_IMAGE_WIDTH = 16_384;
export const MAX_IMAGE_HEIGHT = 16_384;
export const MAX_IMAGE_PIXELS = 80_000_000;

const SUPPORTED_FORMATS = new Set(['png', 'jpeg']);
const REDACTION_RGBA = 0x202020ff;

function requireLocalRegularFile(file) {
    const path = file.get_path();
    if (path === null)
        throw new Error('Only local image files are supported.');
    const info = file.query_info(
        'standard::type,standard::size,standard::is-symlink',
        Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
        null
    );
    if (info.get_is_symlink() || info.get_file_type() !== Gio.FileType.REGULAR)
        throw new Error('The source must be a regular local file.');
    if (info.get_size() <= 0 || info.get_size() > MAX_INPUT_BYTES)
        throw new Error('The image file is empty or too large.');
    return path;
}

function checkedDimensions(width, height) {
    if (!Number.isInteger(width) || !Number.isInteger(height) ||
        width <= 0 || height <= 0 ||
        width > MAX_IMAGE_WIDTH || height > MAX_IMAGE_HEIGHT ||
        width * height > MAX_IMAGE_PIXELS)
        throw new Error('The image dimensions are too large.');
}

export function loadImage(file) {
    const path = requireLocalRegularFile(file);
    const [format, width, height] = GdkPixbuf.Pixbuf.get_file_info(path);
    if (format === null)
        throw new Error('The selected file is not a supported image.');
    const formatName = format.get_name().toLowerCase();
    if (!SUPPORTED_FORMATS.has(formatName))
        throw new Error('Only PNG and JPEG images are supported.');
    checkedDimensions(width, height);

    const loaded = GdkPixbuf.Pixbuf.new_from_file(path);
    checkedDimensions(loaded.get_width(), loaded.get_height());
    const oriented = loaded.apply_embedded_orientation();
    checkedDimensions(oriented.get_width(), oriented.get_height());
    return oriented;
}

export function normalizedRectangle(startX, startY, endX, endY, width, height) {
    if (![startX, startY, endX, endY, width, height].every(Number.isFinite) ||
        width <= 0 || height <= 0)
        return null;
    const left = Math.max(0, Math.min(width, Math.floor(Math.min(startX, endX))));
    const top = Math.max(0, Math.min(height, Math.floor(Math.min(startY, endY))));
    const right = Math.max(0, Math.min(width, Math.ceil(Math.max(startX, endX))));
    const bottom = Math.max(0, Math.min(height, Math.ceil(Math.max(startY, endY))));
    if (right - left < 2 || bottom - top < 2)
        return null;
    return {x: left, y: top, width: right - left, height: bottom - top};
}

export function redactedCopy(source, rectangles) {
    const result = source.copy();
    const width = result.get_width();
    const height = result.get_height();
    for (const rectangle of rectangles) {
        const checked = normalizedRectangle(
            rectangle.x,
            rectangle.y,
            rectangle.x + rectangle.width,
            rectangle.y + rectangle.height,
            width,
            height
        );
        if (checked === null)
            throw new Error('Invalid redaction rectangle.');
        result.new_subpixbuf(
            checked.x,
            checked.y,
            checked.width,
            checked.height
        ).fill(REDACTION_RGBA);
    }
    return result;
}

export function saveRedactedPng(source, rectangles, outputFile) {
    if (rectangles.length === 0)
        throw new Error('At least one redaction is required.');
    const outputPath = outputFile.get_path();
    if (outputPath === null)
        throw new Error('Only a local destination is supported.');
    if (!outputPath.toLowerCase().endsWith('.png'))
        throw new Error('The safe copy must use the .png extension.');

    const redacted = redactedCopy(source, rectangles);
    const [saved, bytes] = redacted.save_to_bufferv('png', [], []);
    if (!saved || bytes.length === 0)
        throw new Error('The PNG could not be encoded.');

    let stream = null;
    let created = false;
    try {
        stream = outputFile.create(Gio.FileCreateFlags.PRIVATE, null);
        created = true;
        const [writtenAll, written] = stream.write_all(bytes, null);
        if (!writtenAll || written !== bytes.length)
            throw new Error('The PNG could not be written completely.');
        if (!stream.close(null))
            throw new Error('The PNG could not be closed safely.');
        stream = null;
    } catch (error) {
        try {
            stream?.close(null);
        } catch (_closeError) {
            // The original write error is more useful.
        }
        if (created) {
            try {
                outputFile.delete(null);
            } catch (_deleteError) {
                // A partial file may remain, but no existing file was overwritten.
            }
        }
        throw error;
    }
}
