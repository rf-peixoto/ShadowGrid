/* Hashcash-style proof of work solved in the browser with WebCrypto (batched). */
window.GridPow = (() => {
  const enc = new TextEncoder();
  function leadingZeroBits(buf) {
    const b = new Uint8Array(buf); let n = 0;
    for (const v of b) { if (v === 0) { n += 8; continue; } n += Math.clz32(v) - 24; break; }
    return n;
  }
  async function solve(challenge, bits, onProgress) {
    const BATCH = 128;
    for (let base = 0; ; base += BATCH) {
      const digests = await Promise.all(Array.from({ length: BATCH }, (_, i) => crypto.subtle.digest('SHA-256', enc.encode(`${challenge}:${base + i}`))));
      for (let i = 0; i < BATCH; i++) if (leadingZeroBits(digests[i]) >= bits) return base + i;
      if (onProgress) onProgress(base + BATCH);
    }
  }
  return { solve };
})();
