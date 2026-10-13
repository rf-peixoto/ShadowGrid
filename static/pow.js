/* Light proof of work for the sign-in and invite forms (needs gate-worker.js loaded first).
   Small enough to solve on the page itself: 2^13 hashes take a few milliseconds. */
window.GridPow = {
  async solve(challenge, bits) {
    if (!window.SGPow) throw new Error('The page did not load completely. Reload it.');
    return window.SGPow.solve(`${challenge}:`, bits);
  },
};
