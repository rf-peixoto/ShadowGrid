/* Proof of work: finds a counter such that SHA-256("<prefix><counter>") starts with `bits` zero bits.
   Pure JavaScript SHA-256 for one 64-byte block (the messages here are always shorter than 56 bytes): several
   times faster than calling WebCrypto once per hash, and it works on plain-HTTP addresses such as
   http://192.168.1.10:5000, where browsers don't offer WebCrypto at all.
   Runs as a Web Worker (the connection check) or as a plain script (window.SGPow, the sign-in forms). */
'use strict';
const K = new Int32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);
const W = new Int32Array(64);
const buf = new Uint8Array(64);

/* First word of SHA-256 over buf[0..len) (len < 56), reusing the message words before word `from`
   (they hold the constant prefix). Only H0 matters for up to 32 leading zero bits. */
function h0(len, from) {
  buf.fill(0, len, 62);
  buf[len] = 0x80;
  buf[62] = (len * 8) >>> 8; buf[63] = (len * 8) & 255;
  for (let i = from; i < 16; i++) W[i] = (buf[i * 4] << 24) | (buf[i * 4 + 1] << 16) | (buf[i * 4 + 2] << 8) | buf[i * 4 + 3];
  for (let i = 16; i < 64; i++) {
    const x = W[i - 15], y = W[i - 2];
    W[i] = (W[i - 16] + (((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3)) + W[i - 7] +
            (((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10))) | 0;
  }
  let a = 0x6a09e667, b = 0xbb67ae85 | 0, c = 0x3c6ef372, d = 0xa54ff53a | 0,
      e = 0x510e527f, f = 0x9b05688c | 0, g = 0x1f83d9ab, hh = 0x5be0cd19;
  for (let i = 0; i < 64; i++) {
    const t1 = (hh + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))) + (g ^ (e & (f ^ g))) + K[i] + W[i]) | 0;
    const t2 = ((((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))) + ((a & b) | (c & (a | b)))) | 0;
    hh = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
  }
  return (a + 0x6a09e667) | 0;
}

function solve(prefix, bits, start, step, report) {
  const pre = new TextEncoder().encode(prefix);
  buf.fill(0); buf.set(pre);
  const from = pre.length >> 2;
  for (let i = 0; i < from; i++) W[i] = (buf[i * 4] << 24) | (buf[i * 4 + 1] << 16) | (buf[i * 4 + 2] << 8) | buf[i * 4 + 3];
  const mask = bits >= 32 ? -1 : ~(-1 >>> bits);      // the top `bits` bits
  const digits = new Uint8Array(20);
  let done = 0, last = Date.now();
  for (let n = start; ; n += step) {
    let v = n, k = 0;                                  // write n in decimal after the prefix
    do { digits[k++] = 48 + (v % 10); v = (v - (v % 10)) / 10; } while (v > 0);
    let len = pre.length;
    while (k > 0) buf[len++] = digits[--k];
    if ((h0(len, from) & mask) === 0) { report({ type: 'found', counter: n, hashes: done + 1 }); return n; }
    if (++done === 16384) {
      const t = Date.now();
      report({ type: 'tick', hashes: done, ms: t - last }); done = 0; last = t;
    }
  }
}

if (typeof WorkerGlobalScope !== 'undefined' && self instanceof WorkerGlobalScope) {
  onmessage = e => { const m = e.data; solve(m.prefix, m.bits, m.start || 0, m.step || 1, msg => postMessage(msg)); };
} else {
  self.SGPow = { solve: (prefix, bits) => solve(prefix, bits, 0, 1, () => {}) };
}
