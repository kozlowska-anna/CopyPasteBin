import Gdk from 'gi://Gdk?version=4.0';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GLibUnix from 'gi://GLibUnix';
import GObject from 'gi://GObject';
import Gtk from 'gi://Gtk?version=4.0';
import System from 'system';

import {languageFromArgs, translate} from './i18n.js';
import {
    loadImage,
    normalizedRectangle,
    saveRedactedPng,
} from './image-redaction-core.js';

const language = languageFromArgs(ARGV);
const t = (message, values = {}) => translate(language, message, values);

function errorText(error) {
    if (error.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.EXISTS))
        return t('Choose a new filename. Existing files are never overwritten.');
    return t('The image could not be processed safely.');
}

const ImageRedactorApplication = GObject.registerClass(
class ImageRedactorApplication extends Gtk.Application {
    constructor() {
        super({application_id: 'io.github.copypastebin.ImageRedactor'});
        this._window = null;
        this._source = null;
        this._sourceFile = null;
        this._rectangles = [];
        this._dragStart = null;
        this._draft = null;
        this._presentSignalId = GLibUnix.signal_add(
            GLib.PRIORITY_DEFAULT,
            10,
            () => {
                this._window?.present();
                return GLib.SOURCE_CONTINUE;
            }
        );
    }

    vfunc_activate() {
        if (this._window !== null) {
            this._window.present();
            return;
        }
        const window = new Gtk.ApplicationWindow({
            application: this,
            title: `CopyPasteBin — ${t('Anonymize image')}`,
            default_width: 1100,
            default_height: 760,
        });
        this._window = window;
        window.connect('close-request', () => {
            this._window = null;
            return false;
        });

        const layout = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 10,
            margin_top: 16,
            margin_bottom: 16,
            margin_start: 16,
            margin_end: 16,
        });
        const actions = new Gtk.Box({spacing: 8});
        const openButton = new Gtk.Button({label: t('Open image')});
        this._undoButton = new Gtk.Button({label: t('Undo last redaction'), sensitive: false});
        this._saveButton = new Gtk.Button({label: t('Save safe PNG copy'), sensitive: false});
        actions.append(openButton);
        actions.append(this._undoButton);
        actions.append(this._saveButton);
        layout.append(actions);

        this._status = new Gtk.Label({
            label: t('Open a PNG or JPEG file, then drag over every area to cover.'),
            xalign: 0,
            wrap: true,
        });
        layout.append(this._status);

        const frame = new Gtk.Frame({hexpand: true, vexpand: true});
        this._canvas = new Gtk.DrawingArea({
            hexpand: true,
            vexpand: true,
            content_width: 640,
            content_height: 480,
        });
        this._canvas.set_draw_func(this._draw.bind(this));
        frame.set_child(this._canvas);
        layout.append(frame);
        window.set_child(layout);

        const drag = new Gtk.GestureDrag();
        drag.connect('drag-begin', (_gesture, x, y) => this._beginDrag(x, y));
        drag.connect('drag-update', (_gesture, dx, dy) => this._updateDrag(dx, dy));
        drag.connect('drag-end', (_gesture, dx, dy) => this._endDrag(dx, dy));
        this._canvas.add_controller(drag);

        openButton.connect('clicked', () => this._chooseInput());
        this._undoButton.connect('clicked', () => this._undo());
        this._saveButton.connect('clicked', () => this._chooseOutput());
        window.present();
    }

    _imageLayout(canvasWidth, canvasHeight) {
        if (this._source === null)
            return null;
        const width = this._source.get_width();
        const height = this._source.get_height();
        const scale = Math.min(canvasWidth / width, canvasHeight / height);
        const displayWidth = width * scale;
        const displayHeight = height * scale;
        return {
            scale,
            x: (canvasWidth - displayWidth) / 2,
            y: (canvasHeight - displayHeight) / 2,
            width: displayWidth,
            height: displayHeight,
        };
    }

    _pointInImage(x, y) {
        const layout = this._imageLayout(this._canvas.get_width(), this._canvas.get_height());
        if (layout === null || x < layout.x || y < layout.y ||
            x > layout.x + layout.width || y > layout.y + layout.height)
            return null;
        return {
            x: (x - layout.x) / layout.scale,
            y: (y - layout.y) / layout.scale,
        };
    }

    _draw(_area, cr, width, height) {
        cr.setSourceRGB(0.12, 0.12, 0.12);
        cr.paint();
        const layout = this._imageLayout(width, height);
        if (layout === null)
            return;
        cr.save();
        cr.translate(layout.x, layout.y);
        cr.scale(layout.scale, layout.scale);
        Gdk.cairo_set_source_pixbuf(cr, this._source, 0, 0);
        cr.paint();
        for (const rectangle of this._rectangles)
            this._drawRectangle(cr, rectangle, false, layout.scale);
        if (this._draft !== null)
            this._drawRectangle(cr, this._draft, true, layout.scale);
        cr.restore();
    }

    _drawRectangle(cr, rectangle, draft, scale) {
        cr.setSourceRGBA(0.125, 0.125, 0.125, draft ? 0.65 : 1);
        cr.rectangle(rectangle.x, rectangle.y, rectangle.width, rectangle.height);
        cr.fillPreserve();
        cr.setSourceRGB(draft ? 0.35 : 0.55, draft ? 0.85 : 0.95, 0.55);
        cr.setLineWidth(2 / scale);
        cr.stroke();
    }

    _beginDrag(x, y) {
        this._dragStart = this._pointInImage(x, y);
        this._draft = null;
    }

    _updateDrag(dx, dy) {
        if (this._dragStart === null)
            return;
        const layout = this._imageLayout(this._canvas.get_width(), this._canvas.get_height());
        this._draft = normalizedRectangle(
            this._dragStart.x,
            this._dragStart.y,
            this._dragStart.x + dx / layout.scale,
            this._dragStart.y + dy / layout.scale,
            this._source.get_width(),
            this._source.get_height()
        );
        this._canvas.queue_draw();
    }

    _endDrag(dx, dy) {
        this._updateDrag(dx, dy);
        if (this._draft !== null) {
            this._rectangles.push(this._draft);
            this._status.label = t('{count} area(s) will be permanently covered in the saved copy.', {
                count: this._rectangles.length,
            });
        }
        this._dragStart = null;
        this._draft = null;
        this._updateActions();
        this._canvas.queue_draw();
    }

    _undo() {
        this._rectangles.pop();
        this._status.label = this._rectangles.length === 0
            ? t('No redactions selected yet.')
            : t('{count} area(s) will be permanently covered in the saved copy.', {
                count: this._rectangles.length,
            });
        this._updateActions();
        this._canvas.queue_draw();
    }

    _updateActions() {
        const hasRedactions = this._source !== null && this._rectangles.length > 0;
        this._undoButton.sensitive = hasRedactions;
        this._saveButton.sensitive = hasRedactions;
    }

    _chooseInput() {
        const chooser = new Gtk.FileChooserNative({
            title: t('Open image'),
            transient_for: this._window,
            action: Gtk.FileChooserAction.OPEN,
            accept_label: t('Open'),
            cancel_label: t('Cancel'),
        });
        const filter = new Gtk.FileFilter();
        filter.set_name(t('PNG and JPEG images'));
        filter.add_mime_type('image/png');
        filter.add_mime_type('image/jpeg');
        chooser.add_filter(filter);
        chooser.connect('response', (_dialog, response) => {
            if (response === Gtk.ResponseType.ACCEPT) {
                try {
                    const file = chooser.get_file();
                    const image = loadImage(file);
                    this._sourceFile = file;
                    this._source = image;
                    this._rectangles = [];
                    this._status.label = t('Drag over every sensitive area. The original file will not be changed.');
                    this._updateActions();
                    this._canvas.queue_draw();
                } catch (error) {
                    this._showError(errorText(error));
                }
            }
            chooser.destroy();
        });
        chooser.show();
    }

    _chooseOutput() {
        const chooser = new Gtk.FileChooserNative({
            title: t('Save safe PNG copy'),
            transient_for: this._window,
            action: Gtk.FileChooserAction.SAVE,
            accept_label: t('Save'),
            cancel_label: t('Cancel'),
        });
        const basename = this._sourceFile.get_basename().replace(/\.[^.]+$/, '');
        chooser.set_current_name(`${basename}-redacted.png`);
        const filter = new Gtk.FileFilter();
        filter.set_name(t('PNG image'));
        filter.add_mime_type('image/png');
        chooser.add_filter(filter);
        chooser.connect('response', (_dialog, response) => {
            if (response === Gtk.ResponseType.ACCEPT) {
                try {
                    saveRedactedPng(this._source, this._rectangles, chooser.get_file());
                    this._status.label = t('Safe PNG copy saved. Metadata from the source was not copied.');
                } catch (error) {
                    this._showError(errorText(error));
                }
            }
            chooser.destroy();
        });
        chooser.show();
    }

    _showError(message) {
        const dialog = new Gtk.MessageDialog({
            transient_for: this._window,
            modal: true,
            message_type: Gtk.MessageType.ERROR,
            buttons: Gtk.ButtonsType.CLOSE,
            text: t('Image anonymization failed'),
            secondary_text: message,
        });
        dialog.connect('response', () => dialog.destroy());
        dialog.present();
    }

    vfunc_shutdown() {
        if (this._presentSignalId !== 0) {
            GLib.source_remove(this._presentSignalId);
            this._presentSignalId = 0;
        }
        this._source = null;
        this._sourceFile = null;
        this._rectangles.length = 0;
        super.vfunc_shutdown();
    }
});

const application = new ImageRedactorApplication();
System.exit(application.run([]));
