/* SightCore: line of sight, cover, light and vision on a ShadowGrid map, with the same rules as the server
   (geometry.py). No DOM: the page uses it directly and sightworker.js runs it off the main thread.

   Unit space: square cells are 1 wide; flat-top hexes have size 1. Rays walk the grid exactly, cell to cell
   (squares: a DDA; hexes: through the edges of each hexagon). Walls (cells without a floor) and closed
   doors block a ray. Cover: 5 points around the viewer's cell to 5 around the target's (25 rays); up to 1/4
   blocked = Cover I, 1/2 = II, 3/4 = III, more = IV, all = no sight.

   Light: 0 bright, 1 dim, 2 dark. Darkness hides what only thermographic vision or ultrasound (50 m) can
   see; smoke gives Blinded I looking through it and II from inside it, unless thermographic (normal smoke)
   or ultrasound sees through; dim light only costs a clear view (the bonus Edge rule). */
(function (root) {
  'use strict';
  const S3 = Math.sqrt(3);
  const LIGHT = ['bright', 'dim', 'dark'];
  const ULTRASOUND_M = 50;
  const SQ_OFF = [[0, -1], [1, 0], [0, 1], [-1, 0]];
  const HEX_EVEN = [[1, 0], [0, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];
  const HEX_ODD = [[1, 1], [0, 1], [-1, 1], [-1, 0], [0, -1], [1, 0]];
  const HEX_CORNERS = [[1, 0], [0.5, S3 / 2], [-0.5, S3 / 2], [-1, 0], [-0.5, -S3 / 2], [0.5, -S3 / 2]];

  const key = (c, r) => c + ',' + r;
  function neighbor(hex, c, r, e) { const o = hex ? ((c & 1) ? HEX_ODD : HEX_EVEN)[e] : SQ_OFF[e]; return [c + o[0], r + o[1]]; }
  function center(hex, c, r) { return hex ? [c * 1.5, S3 * (r + 0.5 * (c & 1))] : [c + 0.5, r + 0.5]; }
  function cellAt(hex, x, y) {
    if (!hex) return [Math.floor(x), Math.floor(y)];
    const q = (2 / 3) * x, rr = (-1 / 3) * x + (S3 / 3) * y;
    const cx = q, cz = rr, cy = -cx - cz;
    let rx = Math.round(cx), ry = Math.round(cy), rz = Math.round(cz);
    const dx = Math.abs(rx - cx), dy = Math.abs(ry - cy), dz = Math.abs(rz - cz);
    if (dx > dy && dx > dz) rx = -ry - rz; else if (dy > dz) ry = -rx - rz; else rz = -rx - ry;
    return [rx, rz + (rx - (rx & 1)) / 2];
  }
  function cellDistance(hex, a, b) {
    if (!hex) return Math.max(Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1]));
    const cube = (c, r) => { const x = c, z = r - (c - (c & 1)) / 2; return [x, -x - z, z]; };
    const A = cube(a[0], a[1]), B = cube(b[0], b[1]);
    return Math.max(Math.abs(A[0] - B[0]), Math.abs(A[1] - B[1]), Math.abs(A[2] - B[2]));
  }
  function samples(hex, c, r, spread) {
    const [x, y] = center(hex, c, r), s = spread * 0.5;
    return [[x, y], [x - s, y - s], [x + s, y - s], [x - s, y + s], [x + s, y + s]];
  }
  function coverLevel(clear, total) {
    if (!clear) return 0;
    const b = 1 - clear / total;
    return b === 0 ? 0 : b <= 0.25 ? 1 : b <= 0.5 ? 2 : b <= 0.75 ? 3 : 4;
  }
  function handles(vision, light, smoke, distM) {
    const v = vision || [], ultra = v.includes('Ultrasound') && (distM || 0) <= ULTRASOUND_M;
    if (smoke === 'thermal' && !ultra) return false;
    if (smoke === 'smoke' && !(ultra || v.includes('Thermographic'))) return false;
    if (light >= 2) return ultra || v.includes('Thermographic');
    if (light === 1) return ultra || v.includes('Thermographic') || v.includes('Low-light');
    return true;
  }

  /* m = { gridType, width, height, cells, ambient?: 'bright'|'dim'|'dark', sources?: [[c, r, radiusCells]],
           cellM?: meters per cell } */
  function world(m) {
    const hex = m.gridType === 'hex', W = m.width, H = m.height, cells = m.cells || {};
    const rooms = new Uint8Array(W * H), closedDoors = new Set(), light = new Map(), smoke = new Map(), secret = new Set();
    const idx = (c, r) => (c >= 0 && r >= 0 && c < W && r < H) ? r * W + c : -1;
    for (const k in cells) {
      const cell = cells[k]; if (!cell) continue;
      const i = k.indexOf(','), c = +k.slice(0, i), r = +k.slice(i + 1);
      const j = idx(c, r);
      if (cell.fill && j >= 0) rooms[j] = 1;
      if (cell.secret) secret.add(k);
      if (cell.light && LIGHT.includes(cell.light)) light.set(k, LIGHT.indexOf(cell.light));
      if (cell.smoke === 'smoke' || cell.smoke === 'thermal') smoke.set(k, cell.smoke);
      if (cell.doors) for (const e in cell.doors) {
        const d = cell.doors[e]; if (!d || d.open) continue;
        const [nc, nr] = neighbor(hex, c, r, +e);
        closedDoors.add(c + ',' + r + '>' + nc + ',' + nr); closedDoors.add(nc + ',' + nr + '>' + c + ',' + r);
      }
    }
    const ambient = Math.max(0, LIGHT.indexOf(m.ambient || 'bright'));
    const cellM = m.cellM || 2;
    const room = (c, r) => { const j = idx(c, r); return j >= 0 && rooms[j] === 1; };
    const closed = (a, b) => closedDoors.size > 0 && closedDoors.has(a[0] + ',' + a[1] + '>' + b[0] + ',' + b[1]);
    function stepOk(a, b) {
      if (!room(b[0], b[1]) || closed(a, b)) return false;
      if (!hex && Math.abs(a[0] - b[0]) === 1 && Math.abs(a[1] - b[1]) === 1) {
        for (const mid of [[b[0], a[1]], [a[0], b[1]]]) if (room(mid[0], mid[1]) && !closed(a, mid) && !closed(mid, b)) return true;
        return false;
      }
      return true;
    }
    /* visit each cell a ray from p (in cell a) to q (in cell b) enters: fn(cell, ok) -> false stops.
       Returns false if a step was blocked. */
    function walk(p, q, a, b, fn) {
      let cur = a;
      if (hex) {
        const dx = q[0] - p[0], dy = q[1] - p[1];
        let t = 0;
        for (let n = 0; n < 4 * (W + H) + 8; n++) {
          if (cur[0] === b[0] && cur[1] === b[1]) return true;
          const [cx, cy] = center(true, cur[0], cur[1]);
          let best = 2, be = -1;
          for (let e = 0; e < 6; e++) {
            const [x1, y1] = HEX_CORNERS[e], [x2, y2] = HEX_CORNERS[(e + 1) % 6];
            const ax = cx + x1, ay = cy + y1, ex = x2 - x1, ey = y2 - y1;
            const den = dx * ey - dy * ex;
            if (Math.abs(den) < 1e-12) continue;
            const s = ((ax - p[0]) * ey - (ay - p[1]) * ex) / den, u = ((ax - p[0]) * dy - (ay - p[1]) * dx) / den;
            if (s > t + 1e-9 && u >= -1e-9 && u <= 1 + 1e-9 && s < best) { best = s; be = e; }
          }
          if (be < 0 || best >= 1) { const ok = (cur[0] === b[0] && cur[1] === b[1]) || stepOk(cur, b); if (fn) fn(b, ok); return ok; }
          const nxt = neighbor(true, cur[0], cur[1], be), ok = stepOk(cur, nxt);
          if (fn && fn(nxt, ok) === false) return ok;
          if (!ok) return false;
          cur = nxt; t = best;
        }
        return true;
      }
      const x0 = p[0], y0 = p[1], dx = q[0] - x0, dy = q[1] - y0;
      let c = cur[0], r = cur[1];
      const sx = dx > 0 ? 1 : -1, sy = dy > 0 ? 1 : -1;
      const tdx = dx ? Math.abs(1 / dx) : Infinity, tdy = dy ? Math.abs(1 / dy) : Infinity;
      let tx = dx ? ((dx > 0 ? c + 1 - x0 : x0 - c) * tdx) : Infinity, ty = dy ? ((dy > 0 ? r + 1 - y0 : y0 - r) * tdy) : Infinity;
      for (let n = 0; n < 2 * (W + H) + 8; n++) {
        if (c === b[0] && r === b[1]) return true;
        let t, nc, nr;
        if (Math.abs(tx - ty) < 1e-9) { t = tx; nc = c + sx; nr = r + sy; tx += tdx; ty += tdy; }
        else if (tx < ty) { t = tx; nc = c + sx; nr = r; tx += tdx; }
        else { t = ty; nc = c; nr = r + sy; ty += tdy; }
        if (t >= 1) { const ok = (c === b[0] && r === b[1]) || stepOk([c, r], b); if (fn) fn(b, ok); return ok; }
        const ok = stepOk([c, r], [nc, nr]);
        if (fn && fn([nc, nr], ok) === false) return ok;
        if (!ok) return false;
        c = nc; r = nr;
      }
      return true;
    }
    const rayClear = (p, q, a, b) => walk(p, q, a, b, null);
    function cover(a, b) {
      if (a[0] === b[0] && a[1] === b[1]) return { los: true, cover: 0, clear: 1, rays: 1 };
      const src = samples(hex, a[0], a[1], 0.6), dst = samples(hex, b[0], b[1], 0.7);
      let clear = 0;
      for (const p of src) for (const q of dst) if (rayClear(p, q, a, b)) clear++;
      return { los: clear > 0, cover: coverLevel(clear, 25), clear, rays: 25 };
    }
    function canSee(a, b) {
      if (a[0] === b[0] && a[1] === b[1]) return true;
      const q = center(hex, b[0], b[1]);
      for (const p of samples(hex, a[0], a[1], 0.6)) if (rayClear(p, q, a, b)) return true;
      return false;
    }
    // light sources: everything a source reaches within its radius is bright
    const lit = new Set();
    for (const s of m.sources || []) {
      const a = [s[0], s[1]], rad = s[2], p = center(hex, a[0], a[1]);
      if (room(a[0], a[1])) lit.add(key(a[0], a[1]));
      for (let c = a[0] - rad - 1; c <= a[0] + rad + 1; c++) for (let r = a[1] - rad - 1; r <= a[1] + rad + 1; r++) {
        if (room(c, r) && cellDistance(hex, a, [c, r]) <= rad && rayClear(p, center(hex, c, r), a, [c, r])) lit.add(key(c, r));
      }
    }
    const level = (c, r) => { const k = key(c, r); return lit.has(k) ? 0 : (light.has(k) ? light.get(k) : ambient); };
    function distM(a, b) {
      const A = center(hex, a[0], a[1]), B = center(hex, b[0], b[1]);
      const d = Math.hypot(A[0] - B[0], A[1] - B[1]);
      return hex ? d / S3 * cellM : d * cellM;
    }
    function smokeBetween(a, b) {
      let worst = null;
      walk(center(hex, a[0], a[1]), center(hex, b[0], b[1]), a, b, (cell, ok) => {
        if (!ok || (cell[0] === b[0] && cell[1] === b[1])) return false;
        const s = smoke.get(key(cell[0], cell[1]));
        if (s === 'thermal' || (s && !worst)) worst = s;
        return true;
      });
      return worst;
    }
    /* how a viewer at a with these eyes sees b: {see, blind 0-3, clear, dark} */
    function view(a, b, vision, blinded) {
      if ((blinded || 0) >= 3) return { see: false, blind: 3, clear: false, dark: false };
      const d = distM(a, b), lv = level(b[0], b[1]);
      if (lv >= 2 && !handles(vision, 2, null, d)) return { see: false, blind: 3, clear: false, dark: true };
      let blind = 0;
      const own = smoke.get(key(a[0], a[1]));
      if (own && !handles(vision, 0, own, d)) blind = 2;
      else { const mid = smoke.get(key(b[0], b[1])) || smokeBetween(a, b); if (mid && !handles(vision, 0, mid, d)) blind = 1; }
      return { see: true, blind, clear: blind === 0 && (lv === 0 || handles(vision, lv, null, d)), dark: false };
    }
    return { hex, W, H, cellM, room, level, smoke, secret, lit, walk, rayClear, cover, canSee, view, distM, center: (c, r) => center(hex, c, r) };
  }

  /* everything a viewer on `from` sees within `radius` steps: seen Map key -> cover, hidden (out of sight),
     dark (in sight lines but too dark for these eyes, part of hidden), far (rooms beyond the radius),
     blind Map key -> Blinded level from smoke. opts: { vision, blinded } (no vision given: walls only) */
  function field(Wd, from, radius, opts) {
    opts = opts || {};
    const a = [from.c, from.r], seen = new Map(), hidden = new Set(), dark = new Set(), far = new Set(), blind = new Map();
    const useEyes = Array.isArray(opts.vision);
    for (let r = 0; r < Wd.H; r++) for (let c = 0; c < Wd.W; c++) {
      if (!Wd.room(c, r)) continue;
      const k = key(c, r);
      if (cellDistance(Wd.hex, a, [c, r]) > radius) { far.add(k); continue; }
      const res = Wd.cover(a, [c, r]);
      if (!res.los) { hidden.add(k); continue; }
      if (useEyes) {
        const v = Wd.view(a, [c, r], opts.vision, opts.blinded);
        if (!v.see) { hidden.add(k); dark.add(k); continue; }
        if (v.blind) blind.set(k, v.blind);
      }
      seen.set(k, res.cover);
    }
    return { from: { c: from.c, r: from.r }, radius, seen, hidden, dark, far, blind };
  }

  /* room cells an area of `radius` meters around a cell reaches (walls block it) */
  function areaCells(Wd, c0, r0, radius) {
    const out = [], rc = Math.ceil(radius / Wd.cellM) + 1, a = [c0, r0], p = Wd.center(c0, r0);
    for (let c = c0 - rc - 1; c <= c0 + rc + 1; c++) for (let r = r0 - rc - 1; r <= r0 + rc + 1; r++) {
      if (!Wd.room(c, r) || Wd.distM(a, [c, r]) > radius + 1e-6) continue;
      if ((c === c0 && r === r0) || Wd.rayClear(p, Wd.center(c, r), a, [c, r])) out.push({ c, r, d: Wd.distM(a, [c, r]) });
    }
    return out;
  }

  const api = { world, field, areaCells, handles, cellDistance, key, LIGHT };
  root.SightCore = api;
})(typeof self !== 'undefined' ? self : window);
