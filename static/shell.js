/* The persistent frame around the app's screens. It holds the music engine (music.js) so the music
   survives moving between screens, keeps the address bar and the tab title in step with the screen
   inside, and steps aside for anything that isn't an app screen (sign-in, the connection check, print). */
(() => {
  'use strict';
  const APP = /^\/(?:|play|game\/[^/]+(?:\/sheet\/[^/]+)?|map\/[^/]+)$/;
  // a frame inside a frame (a browser that doesn't say what it is loading): show the screen itself
  if (window.top !== window) {
    const u = new URL(location.href); u.searchParams.set('embed', '1'); location.replace(u.href); return;
  }
  const frame = document.getElementById('app');
  const clean = s => s.replace(/([?&])embed=1(&|$)/, (_, a, b) => (b ? a : '')).replace(/\?$/, '');
  frame.src = location.pathname + location.search + location.hash;
  let last = location.pathname + location.search + location.hash;
  function follow() {
    let l, doc;
    try { l = frame.contentWindow.location; doc = frame.contentDocument; } catch { return; }   // not ours
    if (!l || l.href === 'about:blank') return;
    if (l.origin !== location.origin || !APP.test(l.pathname)) { location.replace(l.href); return; }
    const url = l.pathname + clean(l.search) + l.hash;
    if (url !== last) { last = url; history.replaceState(null, '', url); }
    if (doc && doc.title && document.title !== doc.title) document.title = doc.title;
  }
  frame.addEventListener('load', () => {
    follow();
    try { frame.contentWindow.focus(); } catch { /* not ours */ }   // keyboard shortcuts work at once
  });
  setInterval(follow, 300);
})();
