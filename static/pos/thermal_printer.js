const ESC = 0x1B;
const GS  = 0x1D;
const LF  = 0x0A;

const EscPos = {

    init:      ()       => [ESC, 0x40],
    feed:      (n = 3)  => [ESC, 0x64, n],
    cut:       ()       => [GS,  0x56, 0x01],   // partial cut
    bold:      (on)     => [ESC, 0x45, on ? 1 : 0],
    underline: (on)     => [ESC, 0x2D, on ? 1 : 0],

    align: (a) => {
        const m = { left: 0, center: 1, right: 2 };
        return [ESC, 0x61, m[a] ?? 0];
    },

    // GS ! n  — 0=normal, 0x10=2×width, 0x01=2×height, 0x11=2×both
    size: (n) => [GS, 0x21, n],

    text: (str) => Array.from(new TextEncoder().encode(str)),
    line: (str) => [...EscPos.text(str), LF],

    separator: (ch = '-', w = 32) => EscPos.line(ch.repeat(w)),

    /**
     * Two-column row padded to `w` characters total.
     *   left  – left-aligned
     *   right – right-aligned
     */
    twoCol(left, right, w = 32) {
        const r   = String(right);
        const l   = String(left);
        const max = w - r.length - 1;
        const lbl = l.length > max ? l.slice(0, max - 1) + '\u2026' : l;
        const pad = Math.max(1, w - lbl.length - r.length);
        return EscPos.line(lbl + ' '.repeat(pad) + r);
    },

    /**
     * Single formatted line.
     *   opts.align  'left' | 'center' | 'right'
     *   opts.bold   boolean
     *   opts.size   'normal' | 'tall' | 'wide' | 'big'
     */
    fmt(str, opts = {}) {
        const { align = 'left', bold = false, size = 'normal' } = opts;
        const sizeMap = { normal: 0x00, tall: 0x01, wide: 0x10, big: 0x11 };
        return [
            ...EscPos.align(align),
            ...EscPos.bold(bold),
            ...EscPos.size(sizeMap[size] ?? 0x00),
            ...EscPos.text(str),
            LF,
            ...EscPos.bold(false),
            ...EscPos.size(0x00),
            ...EscPos.align('left'),
        ];
    },
};


class ThermalPrinter {

    constructor() {
        this.device   = null;
        this.ifaceNum = null;
        this.epNum    = null;
    }

    async connect() {
        if (!navigator.usb) {
            throw new Error(
                'WebUSB is not available. Use Chrome or Edge on a desktop computer.'
            );
        }

        // Re-use an already-paired device when possible
        const paired = await navigator.usb.getDevices();
        if (paired.length > 0) {
            this.device = paired[0];
        } else {
            // Show ALL USB devices so the user can pick their printer model
            this.device = await navigator.usb.requestDevice({ filters: [] });
        }

        if (!this.device.opened) {
            await this.device.open();
        }

        if (this.device.configuration === null) {
            await this.device.selectConfiguration(1);
        }

        // Find a bulk-out or interrupt-out endpoint
        let found = false;
        for (const iface of this.device.configuration.interfaces) {
            if (found) break;
            for (const alt of iface.alternates) {
                if (found) break;
                for (const ep of alt.endpoints) {
                    if (ep.direction === 'out') {
                        try { await this.device.claimInterface(iface.interfaceNumber); }
                        catch (_) { /* already claimed */ }
                        this.ifaceNum = iface.interfaceNumber;
                        this.epNum    = ep.endpointNumber;
                        found = true;
                        break;
                    }
                }
            }
        }

        if (!found) {
            throw new Error(
                'No writable USB endpoint found on this device. ' +
                'Check the cable and make sure the printer is powered on.'
            );
        }
    }

    async disconnect() {
        if (!this.device) return;
        try {
            if (this.ifaceNum !== null) await this.device.releaseInterface(this.ifaceNum);
            if (this.device.opened)     await this.device.close();
        } catch (_) {}
        this.device   = null;
        this.ifaceNum = null;
        this.epNum    = null;
    }

    get isConnected() {
        return !!(this.device?.opened && this.epNum !== null);
    }

    // ── raw write ────────────────────────────────────────────────────────────

    async _write(byteArray) {
        if (!this.isConnected) throw new Error('Printer not connected.');
        const buf   = new Uint8Array(byteArray);
        const CHUNK = 64;
        for (let i = 0; i < buf.length; i += CHUNK) {
            await this.device.transferOut(this.epNum, buf.slice(i, i + CHUNK));
        }
    }

    // ── receipt ──────────────────────────────────────────────────────────────

    /**
     * Print a receipt from a plain JS object.
     *
     * Expected shape (mirrors /sales/<pk>/receipt/data/ JSON):
     * {
     *   store_name, store_address, store_phone, store_tin,
     *   joint, receipt_number, date, cashier, payment_method,
     *   customer_name (nullable),
     *   items: [{ name, qty, unit_price, line_total, is_free_gift, promotion_label }],
     *   subtotal, discount (nullable), discount_label (nullable), total,
     *   tagline, loyalty_points (nullable)
     * }
     */
    async printReceipt(data) {
        const W = 32; // chars per line — 58 mm paper @ 12 cpi

        const b = [
            ...EscPos.init(),
            LF,

            // ── Store header ─────────────────────────────────────────────────
            ...EscPos.fmt(data.store_name || 'GenX POS', { align: 'center', bold: true, size: 'big' }),
            ...EscPos.fmt(data.joint || '',              { align: 'center' }),
        ];

        if (data.store_address) {
            for (const ln of data.store_address.split(/\n|\\n/)) {
                const t = ln.trim();
                if (t) b.push(...EscPos.fmt(t, { align: 'center' }));
            }
        }
        if (data.store_phone) b.push(...EscPos.fmt(data.store_phone, { align: 'center' }));
        if (data.store_tin)   b.push(...EscPos.fmt('TIN: ' + data.store_tin, { align: 'center' }));

        b.push(
            ...EscPos.separator('=', W),

            // ── Sale meta ────────────────────────────────────────────────────
            ...EscPos.line('Receipt : ' + data.receipt_number),
            ...EscPos.line('Date    : ' + data.date),
            ...EscPos.line('Cashier : ' + data.cashier),
            ...EscPos.line('Payment : ' + data.payment_method),
        );

        if (data.customer_name) {
            b.push(...EscPos.line('Customer: ' + data.customer_name));
        }

        b.push(
            ...EscPos.separator('=', W),

            // ── Item column headers ──────────────────────────────────────────
            ...EscPos.bold(true),
            ...EscPos.line('ITEM              QTY  TOTAL'),
            ...EscPos.bold(false),
            ...EscPos.separator('-', W),
        );

        // ── Items ─────────────────────────────────────────────────────────────
        for (const item of (data.items || [])) {
            const qty   = 'x' + item.qty;
            const price = item.is_free_gift ? 'FREE' : '$' + item.line_total;
            const max   = W - qty.length - price.length - 2;
            const name  = String(item.name || '').length > max
                ? String(item.name).slice(0, max - 1) + '\u2026'
                : String(item.name || '');
            const pad = Math.max(1, W - name.length - qty.length - price.length);
            b.push(...EscPos.line(name + ' '.repeat(pad) + qty + ' ' + price));

            if (item.promotion_label) {
                b.push(...EscPos.line('  * ' + item.promotion_label));
            }
        }

        b.push(
            ...EscPos.separator('-', W),

            // ── Totals ───────────────────────────────────────────────────────
            ...EscPos.twoCol('Subtotal', '$' + data.subtotal, W),
        );

        if (data.discount && parseFloat(data.discount) > 0) {
            const lbl = data.discount_label
                ? 'Discount (' + data.discount_label + ')'
                : 'Discount';
            b.push(...EscPos.twoCol(lbl, '-$' + data.discount, W));
        }

        b.push(
            ...EscPos.separator('=', W),
            ...EscPos.bold(true),
            ...EscPos.twoCol('TOTAL', '$' + data.total, W),
            ...EscPos.bold(false),
            ...EscPos.separator('=', W),
        );

        if (data.loyalty_points && data.loyalty_points > 0) {
            b.push(
                LF,
                ...EscPos.fmt('You earned ' + data.loyalty_points + ' loyalty pts!', { align: 'center' }),
            );
        }

        b.push(
            LF,
            ...EscPos.fmt(data.tagline || 'Thank you for your purchase!', { align: 'center' }),
            LF,
            ...EscPos.feed(4),
            ...EscPos.cut(),
        );

        await this._write(b);
    }

    /** Fetch receipt JSON from the server then print. */
    async printFromUrl(url) {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('Failed to load receipt data from server (' + resp.status + ').');
        const data = await resp.json();
        await this.printReceipt(data);
    }
}


// ─────────────────────────────────────────────────────────────────────────────
// PrinterStatusBar  — fixed bottom-right UI widget
// ─────────────────────────────────────────────────────────────────────────────

class PrinterStatusBar {

    constructor() {
        this.printer = new ThermalPrinter();
        this._buildUI();
    }

    _buildUI() {
        if (document.getElementById('gp-bar')) return;

        // ── Styles ────────────────────────────────────────────────────────
        const style = document.createElement('style');
        style.textContent = `
            #gp-bar {
                position: fixed;
                bottom: 14px;
                right: 14px;
                z-index: 9800;
                display: flex;
                align-items: center;
                gap: 8px;
                background: #111827;
                color: #f9fafb;
                padding: 7px 13px;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: .01em;
                cursor: pointer;
                user-select: none;
                box-shadow: 0 4px 14px rgba(0,0,0,.4);
                transition: background .15s;
                font-family: system-ui, -apple-system, sans-serif;
            }
            #gp-bar:hover { background: #1f2937; }
            #gp-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                flex-shrink: 0;
                background: #6b7280;
                transition: background .25s;
            }
            #gp-dot.ok   { background: #10b981; }
            #gp-dot.err  { background: #ef4444; }
            #gp-dot.busy { background: #f59e0b; animation: gp-blink 0.9s infinite; }
            @keyframes gp-blink { 0%,100%{opacity:1} 50%{opacity:.25} }
        `;
        document.head.appendChild(style);

        // ── Element ───────────────────────────────────────────────────────
        const bar = document.createElement('div');
        bar.id = 'gp-bar';
        bar.title = 'Click to connect / disconnect printer';
        bar.innerHTML = '<span id="gp-dot"></span><span id="gp-lbl">Printer: tap to connect</span>';
        bar.addEventListener('click', () => this.toggleConnection());
        document.body.appendChild(bar);
    }

    _set(dot, label) {
        const d = document.getElementById('gp-dot');
        const l = document.getElementById('gp-lbl');
        if (d) d.className = dot;
        if (l) l.textContent = label;
    }

    async toggleConnection() {
        if (this.printer.isConnected) {
            await this.printer.disconnect();
            this._set('err', 'Printer: disconnected');
        } else {
            this._set('busy', 'Connecting\u2026');
            try {
                await this.printer.connect();
                const name = this.printer.device.productName || 'USB Printer';
                this._set('ok', 'Printer: ' + name);
            } catch (err) {
                const msg = err.message.length > 40 ? err.message.slice(0, 40) + '\u2026' : err.message;
                this._set('err', msg);
                console.warn('[GenXPrinter]', err.message);
            }
        }
    }

    async ensureConnected() {
        if (!this.printer.isConnected) {
            await this.toggleConnection();
        }
        return this.printer.isConnected;
    }

    /**
     * Print from a plain JS data object.
     * Called by the POS complete handler.
     */
    async printReceipt(data) {
        if (!await this.ensureConnected()) return;
        this._set('busy', 'Printing\u2026');
        try {
            await this.printer.printReceipt(data);
            this._set('ok', 'Printer: printed \u2713');
            setTimeout(() => {
                if (this.printer.isConnected) {
                    const name = this.printer.device.productName || 'USB Printer';
                    this._set('ok', 'Printer: ' + name);
                }
            }, 2500);
        } catch (err) {
            this._set('err', 'Print error — ' + err.message.slice(0, 28));
            console.error('[GenXPrinter] printReceipt:', err);
            throw err;
        }
    }

    /**
     * Fetch receipt data from /sales/<pk>/receipt/data/ then print.
     * Called by the receipt page.
     */
    async printFromUrl(url) {
        if (!await this.ensureConnected()) return;
        this._set('busy', 'Printing\u2026');
        try {
            await this.printer.printFromUrl(url);
            this._set('ok', 'Printer: printed \u2713');
            setTimeout(() => {
                if (this.printer.isConnected) {
                    const name = this.printer.device.productName || 'USB Printer';
                    this._set('ok', 'Printer: ' + name);
                }
            }, 2500);
        } catch (err) {
            this._set('err', 'Print error — ' + err.message.slice(0, 28));
            console.error('[GenXPrinter] printFromUrl:', err);
            throw err;
        }
    }
}


// ─────────────────────────────────────────────────────────────────────────────
// Boot
// ─────────────────────────────────────────────────────────────────────────────

function _boot() {
    window.GenXPrinter = new PrinterStatusBar();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _boot);
} else {
    _boot();
}