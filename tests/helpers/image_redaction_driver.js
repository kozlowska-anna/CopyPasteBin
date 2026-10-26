import Gio from 'gi://Gio';
import GdkPixbuf from 'gi://GdkPixbuf';
import System from 'system';

import {
    loadImage,
    normalizedRectangle,
    saveRedactedPng,
} from '../../gnome-extension/copypastebin@kozlowska-anna.github.io/image-redaction-core.js';

function createImage(format, path) {
    const image = GdkPixbuf.Pixbuf.new(
        GdkPixbuf.Colorspace.RGB,
        format !== 'jpeg',
        8,
        8,
        6
    );
    image.fill(0xf4f4f4ff);
    image.new_subpixbuf(0, 0, 2, 2).fill(0xff0000ff);
    const keys = format === 'jpeg' ? ['quality'] : [];
    const values = format === 'jpeg' ? ['95'] : [];
    if (!image.savev(path, format, keys, values))
        throw new Error('synthetic image creation failed');
}

function inspectPixel(path, x, y) {
    const image = GdkPixbuf.Pixbuf.new_from_file(path);
    const channels = image.get_n_channels();
    const offset = y * image.get_rowstride() + x * channels;
    const pixels = image.get_pixels();
    const values = Array.from(pixels.slice(offset, offset + channels));
    if (channels === 3)
        values.push(255);
    print(values.join(','));
}

try {
    const [action, ...args] = ARGV;
    if (action === 'create') {
        createImage(args[0], args[1]);
    } else if (action === 'redact') {
        const image = loadImage(Gio.File.new_for_path(args[0]));
        saveRedactedPng(
            image,
            [{x: 2, y: 1, width: 3, height: 3}],
            Gio.File.new_for_path(args[1])
        );
    } else if (action === 'inspect') {
        inspectPixel(args[0], Number(args[1]), Number(args[2]));
    } else if (action === 'normalize') {
        print(JSON.stringify(normalizedRectangle(...args.map(Number))));
    } else {
        throw new Error('unknown action');
    }
} catch (error) {
    printerr(error.message);
    System.exit(1);
}
