// Minimal QR Code encoder for Acrobat JavaScript (ES3/ES5 only: no let,
// const, arrow functions or Array helpers).
//
// Fixed to QR version 2 (25x25), error correction level M, byte mode.
// Capacity: 26 ASCII characters. Used for "注番,納入数", e.g. "YN34214,10000".
//
// qrV2M(text) returns a 25x25 array of booleans (true = dark), or null if the
// text is too long or contains non-ASCII characters.
// qrV2M(text, mask) forces mask pattern 0-7 (used by the tests).

var QR_SIZE = 25;
var QR_DATA_CODEWORDS = 28;
var QR_EC_CODEWORDS = 16;
var QR_MAX_CHARS = 26;

var QR_EXP = [];
var QR_LOG = [];
(function () {
    var x = 1, i;
    for (i = 0; i < 255; i++) {
        QR_EXP[i] = x;
        QR_LOG[x] = i;
        x <<= 1;
        if (x & 0x100) x ^= 0x11d;
    }
})();

function qrGfMul(a, b) {
    if (a === 0 || b === 0) return 0;
    return QR_EXP[(QR_LOG[a] + QR_LOG[b]) % 255];
}

// Generator polynomial for 16 EC codewords, highest degree first.
function qrGenerator() {
    var g = [1], i, j, next;
    for (i = 0; i < QR_EC_CODEWORDS; i++) {
        next = [];
        for (j = 0; j <= g.length; j++) next[j] = 0;
        for (j = 0; j < g.length; j++) {
            next[j] ^= g[j];
            next[j + 1] ^= qrGfMul(g[j], QR_EXP[i]);
        }
        g = next;
    }
    return g;
}

function qrErrorCorrection(data) {
    var gen = qrGenerator();
    var rem = [], i, j, factor;
    for (i = 0; i < QR_EC_CODEWORDS; i++) rem[i] = 0;
    for (i = 0; i < data.length; i++) {
        factor = data[i] ^ rem[0];
        rem.shift();
        rem.push(0);
        for (j = 0; j < QR_EC_CODEWORDS; j++) rem[j] ^= qrGfMul(gen[j + 1], factor);
    }
    return rem;
}

function qrDataCodewords(text) {
    var bits = [], i, k, c, bytes = [];
    function put(value, length) {
        for (k = length - 1; k >= 0; k--) bits.push((value >>> k) & 1);
    }
    put(4, 4);              // byte mode
    put(text.length, 8);    // character count
    for (i = 0; i < text.length; i++) put(text.charCodeAt(i), 8);
    for (i = 0; i < 4 && bits.length < QR_DATA_CODEWORDS * 8; i++) bits.push(0);
    while (bits.length % 8 !== 0) bits.push(0);
    for (i = 0; i < bits.length; i += 8) {
        c = 0;
        for (k = 0; k < 8; k++) c = (c << 1) | bits[i + k];
        bytes.push(c);
    }
    for (i = 0; bytes.length < QR_DATA_CODEWORDS; i++) bytes.push(i % 2 === 0 ? 0xec : 0x11);
    return bytes;
}

function qrMaskBit(mask, r, c) {
    switch (mask) {
        case 0: return (r + c) % 2 === 0;
        case 1: return r % 2 === 0;
        case 2: return c % 3 === 0;
        case 3: return (r + c) % 3 === 0;
        case 4: return (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0;
        case 5: return (r * c) % 2 + (r * c) % 3 === 0;
        case 6: return ((r * c) % 2 + (r * c) % 3) % 2 === 0;
        default: return ((r * c) % 3 + (r + c) % 2) % 2 === 0;
    }
}

// Function patterns: finders, separators, timing, alignment, dark module.
// Returns [modules, reserved], where reserved marks cells data must skip.
function qrBaseMatrix() {
    var n = QR_SIZE, m = [], res = [], r, c, i;
    for (r = 0; r < n; r++) {
        m[r] = [];
        res[r] = [];
        for (c = 0; c < n; c++) { m[r][c] = false; res[r][c] = false; }
    }
    function finder(top, left) {
        var dr, dc, rr, cc, d;
        for (dr = -1; dr <= 7; dr++) {
            for (dc = -1; dc <= 7; dc++) {
                rr = top + dr; cc = left + dc;
                if (rr < 0 || rr >= n || cc < 0 || cc >= n) continue;
                d = Math.max(Math.abs(dr - 3), Math.abs(dc - 3));
                m[rr][cc] = d !== 2 && d !== 4;
                res[rr][cc] = true;
            }
        }
    }
    finder(0, 0);
    finder(0, n - 7);
    finder(n - 7, 0);
    for (i = 8; i < n - 8; i++) {
        m[6][i] = m[i][6] = i % 2 === 0;
        res[6][i] = res[i][6] = true;
    }
    for (r = -2; r <= 2; r++) {
        for (c = -2; c <= 2; c++) {
            m[18 + r][18 + c] = Math.max(Math.abs(r), Math.abs(c)) !== 1;
            res[18 + r][18 + c] = true;
        }
    }
    // Format information areas.
    for (i = 0; i < 9; i++) { res[8][i] = true; res[i][8] = true; }
    for (i = 0; i < 8; i++) { res[8][n - 1 - i] = true; res[n - 1 - i][8] = true; }
    m[n - 8][8] = true;
    return [m, res];
}

function qrFormatBits(mask) {
    var data = (0 << 3) | mask;   // level M = 00
    var v = data << 10, i;
    for (i = 14; i >= 10; i--) if ((v >>> i) & 1) v ^= 0x537 << (i - 10);
    return ((data << 10) | v) ^ 0x5412;
}

function qrPlaceFormat(m, mask) {
    var n = QR_SIZE, bits = qrFormatBits(mask), i, b;
    for (i = 0; i < 15; i++) {
        b = ((bits >>> i) & 1) === 1;
        if (i < 6) m[i][8] = b;
        else if (i < 8) m[i + 1][8] = b;
        else m[n - 15 + i][8] = b;
        if (i < 8) m[8][n - i - 1] = b;
        else if (i < 9) m[8][15 - i] = b;
        else m[8][15 - i - 1] = b;
    }
    m[n - 8][8] = true;
}

function qrPenalty(m) {
    var n = QR_SIZE, score = 0, r, c, run, dark = 0, k, line;
    for (r = 0; r < n; r++) {
        for (k = 0; k < 2; k++) {
            run = 1;
            for (c = 1; c < n; c++) {
                var same = k === 0 ? m[r][c] === m[r][c - 1] : m[c][r] === m[c - 1][r];
                if (same) { run++; if (run === 5) score += 3; else if (run > 5) score++; }
                else run = 1;
            }
        }
    }
    for (r = 0; r < n - 1; r++)
        for (c = 0; c < n - 1; c++)
            if (m[r][c] === m[r][c + 1] && m[r][c] === m[r + 1][c] && m[r][c] === m[r + 1][c + 1]) score += 3;
    for (r = 0; r < n; r++) {
        for (k = 0; k < 2; k++) {
            line = "";
            for (c = 0; c < n; c++) line += (k === 0 ? m[r][c] : m[c][r]) ? "1" : "0";
            for (c = line.indexOf("1011101"); c !== -1; c = line.indexOf("1011101", c + 1)) {
                if (line.substr(c - 4, 4) === "0000" || line.substr(c + 7, 4) === "0000") score += 40;
            }
        }
    }
    for (r = 0; r < n; r++) for (c = 0; c < n; c++) if (m[r][c]) dark++;
    score += Math.floor(Math.abs(dark * 20 - n * n * 10) / (n * n)) * 10;
    return score;
}

function qrBuild(codewords, mask) {
    var base = qrBaseMatrix(), m = base[0], res = base[1], n = QR_SIZE;
    var bitIndex = 0, total = codewords.length * 8;
    var col, row, i, c, up = true, bit;
    for (col = n - 1; col > 0; col -= 2) {
        if (col === 6) col--;
        for (i = 0; i < n; i++) {
            row = up ? n - 1 - i : i;
            for (c = 0; c < 2; c++) {
                if (res[row][col - c]) continue;
                bit = false;
                if (bitIndex < total) bit = ((codewords[bitIndex >>> 3] >>> (7 - (bitIndex & 7))) & 1) === 1;
                bitIndex++;
                m[row][col - c] = bit !== qrMaskBit(mask, row, col - c);
            }
        }
        up = !up;
    }
    qrPlaceFormat(m, mask);
    return m;
}

function qrV2M(text, forcedMask) {
    var i, data, codewords, best = null, bestScore = 0, mask, m, s;
    text = String(text);
    if (text.length > QR_MAX_CHARS) return null;
    for (i = 0; i < text.length; i++) if (text.charCodeAt(i) > 0x7e || text.charCodeAt(i) < 0x20) return null;
    data = qrDataCodewords(text);
    codewords = data.concat(qrErrorCorrection(data));
    if (forcedMask !== undefined) return qrBuild(codewords, forcedMask);
    for (mask = 0; mask < 8; mask++) {
        m = qrBuild(codewords, mask);
        s = qrPenalty(m);
        if (best === null || s < bestScore) { best = m; bestScore = s; }
    }
    return best;
}
