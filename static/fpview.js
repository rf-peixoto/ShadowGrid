/* FPView: a first-person ("pseudo 3D") view of a ShadowGrid map, drawn by ray casting like the early
   90s dungeon crawlers. Rooms are cells with a floor; anything else is wall; doors stand on cell edges.
   The player's fog of war applies: a wall shows only where there is one (the server tells which edges of an
   explored cell are walls); past the edge of what the runner has explored hangs a fog curtain instead.

   Rendered at a low internal resolution into an ImageData (fast, and pixelated on purpose), then scaled
   up; markers and runners are upright sprites, hidden behind walls with a per-column depth buffer.

   FPView.render(ctx, W, H, dpr, o)   o = { map, view, cam: {x, y, a} (map pixels, radians), sprites, eyes,
                                          overlay: {"c,r": [r, g, b, a]} tints on the floor (sight, range, reach, areas) }
   FPView.pick(sx, sy)                -> the sprite under a CSS-pixel point, nearest first, or null
   FPView.angleOf(map, facing)        -> the angle of a facing (an edge index) on this grid */
window.FPView = (() => {
  'use strict';
  const { key, geom, visibility, drawMarker, drawToken, drawCM, drawStatuses } = GridCore;
  const FOV = 66 * Math.PI / 180, PLANE = Math.tan(FOV / 2);
  const MAX_DIST = 40, FOG_DIST = 15, WALL_H = 1.0, EYE = 0.5;
  const buf = document.createElement('canvas'), bctx = buf.getContext('2d');
  let img = null, zbuf = new Float32Array(1), picks = [];
  const rgbCache = new Map(), spriteCache = new Map();

  function rgb(hex) {
    let v = rgbCache.get(hex);
    if (!v) {
      const s = String(hex || '#000000').replace('#', '');
      const n = parseInt(s.length === 3 ? s.split('').map(x => x + x).join('') : s.slice(0, 6), 16) || 0;
      v = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
      rgbCache.set(hex, v);
    }
    return v;
  }
  const mixc = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];

  function angleOf(map, facing) {
    const deg = map.gridType === 'hex' ? [30, 90, 150, 210, 270, 330] : [270, 0, 90, 180];
    return deg[((facing % deg.length) + deg.length) % deg.length] * Math.PI / 180;
  }

  /* the world as seen by this viewer: is a cell a room they can see into, and how should it look */
  /* light at a cell for these eyes: {k: how much darker, tint: colour to lean toward or null}.
     eyes null: the GM's view (light shown, nobody blinded) */
  const THERMAL = [70, 34, 120], SONAR = [96, 110, 118];
  function tone(lv, eyes) {
    if (!lv) return null;
    if (!eyes) return { k: lv === 1 ? 0.25 : 0.5, tint: null };
    const handles = typeof SightCore !== 'undefined' ? SightCore.handles : () => false;
    if (handles(eyes, lv, null, 0)) {
      if (lv === 2) return eyes.includes('Thermographic') ? { k: 0.15, tint: THERMAL } : { k: 0.2, tint: SONAR };
      return { k: 0.12, tint: null };                    // low-light: a little grainy, clear enough
    }
    return lv === 1 ? { k: 0.45, tint: null } : { k: 0.9, tint: null };
  }
  function toned(c3, t) {
    if (!t) return c3;
    const x = t.tint ? mixc(c3, t.tint, 0.55) : c3;
    return mixc(x, [0, 0, 0], t.k);
  }
  function world(map, view, eyes, overlayArg) {
    const G = geom(map), cells = map.data.cells, cs = G.cs, col = map.settings.colors;
    const cellInfo = new Map();
    const amb = view.mode === 'player' ? 0 : Math.max(0, ['bright', 'dim', 'dark'].indexOf((map.settings && map.settings.ambientLight) || 'bright'));
    const lightOf = view.light || ((c, r, cell) => cell.light ? Math.max(0, ['bright', 'dim', 'dark'].indexOf(cell.light)) : amb);
    const seesSmoke = kind => !!eyes && typeof SightCore !== 'undefined' && SightCore.handles(eyes, 0, kind, 0);
    const overlay = overlayArg || null;
    function info(c, r) {
      const k = key(c, r);
      let v = cellInfo.get(k);
      if (v) return v;
      const cell = G.inBounds(c, r) ? cells[k] : null;
      const vis = cell ? visibility(view, k, cell) : 'hidden';
      if (!cell || vis === 'hidden') v = { room: false, unknown: view.mode === 'player', c, r };
      else if (!cell.fill) v = { room: false, unknown: false, c, r };
      else {
        const fill = rgb(cell.fill), dim = vis === 'dim', t = tone(lightOf(c, r, cell), eyes);
        v = { room: true, c, r, dim, cell, tone: t, smoke: cell.smoke && !seesSmoke(cell.smoke) ? cell.smoke : null,
              floor: toned(dim ? mixc(fill, rgb(col.revealedTint), 0.6) : fill, t),
              trim: toned(rgb(cell.border || col.cellBorder), t), ceil: toned(mixc(fill, [0, 0, 0], 0.82), t) };
        if (v.smoke) v.floor = mixc(v.floor, [150, 158, 162], 0.35);
        v.wallBase = v.floor;                          // walls keep the room's colour; overlays tint the floor only
        const ov = overlay && overlay.get(k);
        if (ov && ov[3] > 0.01) v.floor = mixc(v.floor, ov, Math.min(0.85, ov[3] * 1.35));
        // edges that open onto what this runner hasn't explored: the fog creeps in over the floor there
        if (view.mode === 'player') {
          let m = 0;
          for (let e = 0; e < G.edgeCount; e++) {
            const n = G.neighbor(c, r, e), nk = key(n.c, n.r), nc = G.inBounds(n.c, n.r) ? cells[nk] : null;
            if (nc && nc.fill && visibility(view, nk, nc) !== 'hidden') continue;
            if (wallAt(v, e, n.c, n.r)) continue;
            const d = GridCore.doorOnEdge(G, cells, c, r, e);
            if (!d || d.open) m |= 1 << e;
          }
          v.fogE = m;
        }
      }
      cellInfo.set(k, v);
      return v;
    }
    // a door on the edge between two adjacent cells, from either side
    function doorBetween(a, b) {
      for (let e = 0; e < G.edgeCount; e++) {
        const n = G.neighbor(a.c, a.r, e);
        if (n.c === b.c && n.r === b.r) return GridCore.doorOnEdge(G, cells, a.c, a.r, e);
      }
      return null;
    }
    /* is there a real wall on edge e of an explored cell (from), toward a cell this viewer can't see?
       Players' cells carry a bitmask of their wall edges ("w"); the GM's copy of the map knows outright.
       Unexplored secret cells count as walls. */
    function wallAt(from, e, c, r) {
      if (!from || !from.room) return true;
      if (from.cell && from.cell.w != null) return !!(from.cell.w & (1 << e));
      if (!G.inBounds(c, r)) return true;
      const t = cells[key(c, r)];
      return !t || !t.fill || !!t.secret;
    }
    return { G, cs, col, info, doorBetween, cells, wallAt };
  }

  /* cast one ray from (px, py) in cell units along (dx, dy); square grids walk the cells exactly (DDA),
     hex grids march in small steps. Returns {dist, kind, u, side, door, from} */
  function castSquare(W, px, py, dx, dy) {
    let c = Math.floor(px), r = Math.floor(py);
    const stepC = dx < 0 ? -1 : 1, stepR = dy < 0 ? -1 : 1;
    const ddx = dx === 0 ? 1e30 : Math.abs(1 / dx), ddy = dy === 0 ? 1e30 : Math.abs(1 / dy);
    let sx = dx < 0 ? (px - c) * ddx : (c + 1 - px) * ddx, sy = dy < 0 ? (py - r) * ddy : (r + 1 - py) * ddy;
    let from = W.info(c, r), side = 0, dist = 0, smoke = from.smoke ? 1 : 0;
    for (let i = 0; i < 200; i++) {
      if (sx < sy) { dist = sx; sx += ddx; c += stepC; side = 0; } else { dist = sy; sy += ddy; r += stepR; side = 1; }
      if (dist > MAX_DIST) return { dist: MAX_DIST, kind: 'far', smoke };
      const to = W.info(c, r);
      const door = from.room ? W.doorBetween(from, to) : null;
      const hx = px + dx * dist, hy = py + dy * dist;
      const u = side === 0 ? hy - Math.floor(hy) : hx - Math.floor(hx);
      if (door && !door.open) return { dist, kind: 'door', door, u, side, from, smoke, hx, hy };
      if (!to.room) {
        const e = side === 0 ? (stepC > 0 ? 1 : 3) : (stepR > 0 ? 2 : 0);
        return { dist, kind: to.unknown && !W.wallAt(from, e, c, r) ? 'fog' : 'wall', u, side, from, openDoor: door, smoke, hx, hy };
      }
      if (to.smoke) smoke++;
      from = to;
    }
    return { dist: MAX_DIST, kind: 'far', smoke };
  }
  /* hexes: walk from hexagon to hexagon through the edge the ray leaves by (exact, like the squares' DDA);
     u is the position along that edge, so seams and door slits sit where they should */
  const HEXC = [0, 1, 2, 3, 4, 5].map(i => [0.5 * Math.cos(Math.PI / 3 * i), 0.5 * Math.sin(Math.PI / 3 * i)]);
  function castHex(W, px, py, dx, dy) {
    const G = W.G, cs = W.cs;
    let cur = G.pointToCell(px * cs, py * cs);
    if (!cur) return { dist: 0.05, kind: 'wall', u: 0.5, side: 0, from: { room: false } };
    let from = W.info(cur.c, cur.r), t = 0, smoke = from.smoke ? 1 : 0;
    for (let n = 0; n < 600; n++) {
      const ctr = G.cellCenter(cur.c, cur.r), cx = ctr.x / cs, cy = ctr.y / cs;
      let best = Infinity, be = -1, bu = 0;
      for (let e = 0; e < 6; e++) {
        const [x1, y1] = HEXC[e], [x2, y2] = HEXC[(e + 1) % 6];
        const ax = cx + x1, ay = cy + y1, ex = x2 - x1, ey = y2 - y1;
        const den = dx * ey - dy * ex;
        if (Math.abs(den) < 1e-12) continue;
        const s = ((ax - px) * ey - (ay - py) * ex) / den, u = ((ax - px) * dy - (ay - py) * dx) / den;
        if (s > t + 1e-7 && u >= -1e-6 && u <= 1 + 1e-6 && s < best) { best = s; be = e; bu = Math.max(0, Math.min(1, u)); }
      }
      if (be < 0 || best > MAX_DIST) return { dist: MAX_DIST, kind: 'far', smoke };
      const nb = G.neighbor(cur.c, cur.r, be), to = W.info(nb.c, nb.r);
      const door = from.room ? GridCore.doorOnEdge(G, W.cells, cur.c, cur.r, be) : null;
      if (door && !door.open) return { dist: best, kind: 'door', door, u: bu, side: be, edge: be, from, smoke };
      if (!to.room) return { dist: best, kind: to.unknown && !W.wallAt(from, be, nb.c, nb.r) ? 'fog' : 'wall', u: bu, side: be, edge: be, from, openDoor: door, smoke, hx: px + dx * best, hy: py + dy * best };
      if (to.smoke) smoke++;
      cur = nb; from = to; t = best;
    }
    return { dist: MAX_DIST, kind: 'far', smoke };
  }

  /* how much fog covers a floor point near an edge that opens onto unexplored ground (0..0.9) */
  const HEXDEG = [30, 90, 150, 210, 270, 330];
  function fogCreep(G, cell, fx, fy, hex) {
    let k = 0;
    if (!hex) {
      const ex = Math.min(1, Math.max(0, fx - cell.c)), ey = Math.min(1, Math.max(0, fy - cell.r)), d = [ey, 1 - ex, 1 - ey, ex];
      for (let e = 0; e < 4; e++) if (cell.fogE & (1 << e)) k = Math.max(k, 1 - d[e] / 0.75);
    } else {
      const ctr = G.cellCenter(cell.c, cell.r), dx = fx - ctr.x / G.cs, dy = fy - ctr.y / G.cs;
      const ang = ((Math.atan2(dy, dx) * 180 / Math.PI) + 360) % 360;
      let e = 0, best = 999;
      for (let i = 0; i < 6; i++) { const dd = Math.abs(((ang - HEXDEG[i] + 540) % 360) - 180); if (dd < best) { best = dd; e = i; } }
      if (cell.fogE & (1 << e)) k = (Math.hypot(dx, dy) - 0.1) / 0.45;
    }
    k = Math.max(0, Math.min(1, k));
    return k * k * 0.9;
  }
  /* smooth 2D value noise for the fog curtain */
  function fogNoise(x, y) {
    const h = (i, j) => { const t = Math.sin(i * 127.1 + j * 311.7) * 43758.5453; return t - Math.floor(t); };
    const x0 = Math.floor(x), y0 = Math.floor(y), fx = x - x0, fy = y - y0, sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
    const a = h(x0, y0) + (h(x0 + 1, y0) - h(x0, y0)) * sx, b = h(x0, y0 + 1) + (h(x0 + 1, y0 + 1) - h(x0, y0 + 1)) * sx;
    return a + (b - a) * sy;
  }
  function wallColor(hit, v, colors) {
    // v: 0 at the top of the wall, 1 at the bottom
    const u = hit.u;
    if (hit.kind === 'door') {
      const dc = toned(rgb(hit.door.color || colors.doorDefault), hit.from && hit.from.tone);
      const slit = Math.abs(u - 0.5) < 0.035 && v > 0.08;
      const frame = u < 0.07 || u > 0.93 || v < 0.06;
      return slit ? mixc(dc, [0, 0, 0], 0.75) : frame ? mixc(dc, [255, 255, 255], 0.25) : mixc(dc, [0, 0, 0], 0.35 + 0.1 * ((v * 6) % 1 < 0.08));
    }
    const from = hit.from && hit.from.room ? hit.from : null;
    const base = from ? mixc(mixc(from.wallBase || from.floor, [8, 14, 16], 0.3), from.trim, 0.08) : [30, 50, 56];
    const trim = from ? from.trim : rgb(colors.cellBorder);
    if (v < 0.035 || (v > 0.955)) return trim;                                  // neon trim top and bottom
    if (Math.abs(u - 0.5) < 0.012 || u < 0.012 || u > 0.988) return mixc(base, [0, 0, 0], 0.45);   // panel seams
    return mixc(base, [0, 0, 0], 0.08 * Math.floor(v * 5) % 2);
  }

  function spriteImage(s, colors) {
    const k = s.kind + '|' + (s.type || '') + '|' + (s.color || '') + '|' + (s.me ? 1 : 0) + '|' + JSON.stringify(s.cm || null) + '|' + JSON.stringify(s.statuses || null);
    let c = spriteCache.get(k);
    if (c) return c;
    if (spriteCache.size > 200) spriteCache.clear();
    c = document.createElement('canvas'); c.width = 128; c.height = 176;
    const g = c.getContext('2d');
    if (s.kind === 'marker') {
      g.fillStyle = 'rgba(0,0,0,.45)'; g.beginPath(); g.ellipse(64, 166, 34, 9, 0, 0, Math.PI * 2); g.fill();
      g.strokeStyle = 'rgba(0,0,0,.6)'; g.lineWidth = 4; g.beginPath(); g.moveTo(64, 166); g.lineTo(64, 104); g.stroke();
      drawMarker(g, 64, 76, 78, s.type, s.color || colors.markerDefault, colors.markerText, false);
    } else {
      g.fillStyle = 'rgba(0,0,0,.45)'; g.beginPath(); g.ellipse(64, 166, 34, 9, 0, 0, Math.PI * 2); g.fill();
      g.strokeStyle = 'rgba(0,0,0,.6)'; g.lineWidth = 4; g.beginPath(); g.moveTo(64, 166); g.lineTo(64, 110); g.stroke();
      drawToken(g, 64, 76, 80, Object.assign({}, s, { cm: null, statuses: null }), colors, false);
    }
    if (s.cm) drawCM(g, 64, 22, 80, s.cm, false);
    if (s.statuses) drawStatuses(g, 64, s.cm ? 8 : 20, 80, s.statuses);
    spriteCache.set(k, c);
    return c;
  }

  function render(ctx, W, H, dpr, o) {
    const map = o.map, colors = map.settings.colors, Wd = world(map, o.view, o.eyes || null, o.overlay || null), G = Wd.G, cs = G.cs;
    const RW = Math.max(200, Math.min(560, Math.round(W * dpr / (W > 1100 ? 3 : 2.4)))), RH = Math.max(120, Math.round(RW * H / W));
    if (buf.width !== RW || buf.height !== RH) { buf.width = RW; buf.height = RH; img = bctx.createImageData(RW, RH); zbuf = new Float32Array(RW); }
    const px = o.cam.x / cs, py = o.cam.y / cs, a = o.cam.a;
    // camera: direction + a plane at distance 1 whose half-width spans half the screen (66° across);
    // pixels are square, so a wall 1 cell high at distance d is f / d pixels tall, eye at half its height
    // focal length: 66° across, but never less than ~50° top to bottom (wide, short panels) nor more than 100° across
    const f = Math.max((RW / 2) / Math.tan(50 * Math.PI / 180), Math.min((RW / 2) / PLANE, (RH / 2) / Math.tan(25 * Math.PI / 180)));
    const PL = (RW / 2) / f;
    const dirX = Math.cos(a), dirY = Math.sin(a), plX = -dirY * PL, plY = dirX * PL;
    const data = img.data, half = RH / 2, fogC = rgb(colors.fog), sky = mixc(rgb(colors.background), [0, 0, 0], 0.35);
    const showGrid = map.settings.showGrid !== false, gridC = rgb(colors.grid), hex = G.hex;

    // ---- floor and ceiling (mirror rows share the same spot on the map)
    const rx0 = dirX - plX, ry0 = dirY - plY, rx1 = dirX + plX, ry1 = dirY + plY;
    for (let y = Math.floor(half) + 1; y < RH; y++) {
      const rowDist = (f * EYE) / (y - half);
      const fog = Math.min(1, Math.pow(rowDist / FOG_DIST, 1.15));
      let fx = px + rowDist * rx0, fy = py + rowDist * ry0;
      const sxp = rowDist * (rx1 - rx0) / RW, syp = rowDist * (ry1 - ry0) / RW;
      const yc = RH - 1 - y;
      for (let x = 0; x < RW; x++, fx += sxp, fy += syp) {
        let floor, ceil;
        let cell;
        if (!hex) cell = Wd.info(Math.floor(fx), Math.floor(fy));
        else { const p = G.pointToCell(fx * cs, fy * cs); cell = p ? Wd.info(p.c, p.r) : { room: false }; }
        if (cell.room) {
          floor = cell.floor; ceil = cell.ceil;
          if (showGrid && !hex) {
            const ex = fx - Math.floor(fx), ey = fy - Math.floor(fy), w = 0.025 + rowDist * 0.004;
            if (ex < w || ex > 1 - w || ey < w || ey > 1 - w) floor = mixc(floor, gridC, 0.7);
          }
          if (cell.fogE) {
            const k = fogCreep(G, cell, fx, fy, hex);
            if (k > 0) { floor = mixc(floor, fogC, k); ceil = mixc(ceil, fogC, k); }
          }
        } else if (cell.unknown) { floor = fogC; ceil = fogC; }
        else { floor = fogC; ceil = sky; }
        const f = mixc(floor, fogC, fog), cc = mixc(ceil, fogC, fog);
        let i = (y * RW + x) * 4; data[i] = f[0]; data[i + 1] = f[1]; data[i + 2] = f[2]; data[i + 3] = 255;
        i = (yc * RW + x) * 4; data[i] = cc[0]; data[i + 1] = cc[1]; data[i + 2] = cc[2]; data[i + 3] = 255;
      }
    }
    // the rows at the horizon the floor pass doesn't reach (the floor is infinitely far there): fog
    for (let y = Math.max(0, Math.floor(half) - 1); y <= Math.min(RH - 1, Math.floor(half)); y++) {
      for (let x = 0; x < RW; x++) { const i = (y * RW + x) * 4; data[i] = fogC[0]; data[i + 1] = fogC[1]; data[i + 2] = fogC[2]; data[i + 3] = 255; }
    }

    // ---- walls and doors
    for (let x = 0; x < RW; x++) {
      const camX = 2 * x / RW - 1, dx = dirX + plX * camX, dy = dirY + plY * camX;
      const len = Math.hypot(dx, dy);
      const hit = hex ? castHex(Wd, px, py, dx / len, dy / len) : castSquare(Wd, px, py, dx, dy);
      let dist = hit.dist;
      if (hex) dist = dist * ((dx / len) * dirX + (dy / len) * dirY);   // fisheye correction
      if (!hex && hit.kind !== 'far') dist = hit.dist;                   // DDA distance is already perpendicular
      zbuf[x] = hit.kind === 'far' ? MAX_DIST : dist;
      if (hit.kind === 'far') continue;
      const d = Math.max(0.05, dist);
      const top = half - f * (WALL_H - EYE) / d, bot = half + f * EYE / d;
      if (hit.kind === 'fog') {
        // the edge of what this runner has explored: a soft bank of fog, no wall; it thins out at the top
        // and bottom and drifts a little (value noise across the screen)
        const ext = (bot - top) * 0.35, fy0 = Math.max(0, Math.ceil(top - ext)), fy1 = Math.min(RH - 1, Math.floor(bot + ext * 0.25));
        const near = Math.max(0, 1 - dist / FOG_DIST);
        for (let y = fy0; y <= fy1; y++) {
          const v = (y - (top - ext)) / (bot + ext * 0.25 - (top - ext));
          const edge = Math.min(1, Math.min(v, 1 - v) * 3.2);
          const n = fogNoise((hit.hx + hit.hy) * 2.3, v * 3.2);   // anchored to the boundary: no swimming as you turn
          const al = Math.min(1, edge * 1.6) * (0.9 + 0.1 * n);
          const i = (y * RW + x) * 4, c = mixc(fogC, [150, 168, 172], 0.03 + 0.09 * n * (0.4 + 0.6 * near));
          data[i] = data[i] + (c[0] - data[i]) * al; data[i + 1] = data[i + 1] + (c[1] - data[i + 1]) * al; data[i + 2] = data[i + 2] + (c[2] - data[i + 2]) * al;
        }
        continue;
      }
      const y0 = Math.max(0, Math.ceil(top)), y1 = Math.min(RH - 1, Math.floor(bot));
      // facets: square walls by side, hex walls by the direction their edge faces (light from the north-west)
      const shade = hex ? 0.7 + 0.3 * Math.max(0, Math.cos((60 * (hit.edge || 0) + 30) * Math.PI / 180 + 2.1)) : (hit.side ? 0.78 : 1);
      const fog = Math.min(1, Math.pow(dist / FOG_DIST, 1.15) + 0.22 * (hit.smoke || 0));
      // walls fade into the fog where their room opens onto unexplored ground
      const creep = hit.kind === 'wall' && hit.from && hit.from.fogE && hit.hx != null ? fogCreep(G, hit.from, hit.hx, hit.hy, hex) : 0;
      for (let y = y0; y <= y1; y++) {
        const v = (y - top) / (bot - top);
        let c = wallColor(hit, v, colors);
        c = mixc([c[0] * shade, c[1] * shade, c[2] * shade], fogC, Math.min(1, fog + creep));
        const i = (y * RW + x) * 4; data[i] = c[0]; data[i + 1] = c[1]; data[i + 2] = c[2]; data[i + 3] = 255;
      }
    }
    bctx.putImageData(img, 0, 0);
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(buf, 0, 0, Math.round(W * dpr), Math.round(H * dpr));

    // ---- sprites: markers and runners, far to near, clipped column by column against the walls
    const sx = W * dpr / RW, sy = H * dpr / RH;
    const items = [];
    for (const s of o.sprites || []) {
      const rxs = s.x / cs - px, rys = s.y / cs - py;
      const inv = 1 / (plX * dirY - dirX * plY);
      const tX = inv * (dirY * rxs - dirX * rys), tY = inv * (-plY * rxs + plX * rys);
      if (tY <= 0.38 || tY > MAX_DIST) continue;
      items.push({ s, tX, tY });
    }
    items.sort((p, q) => q.tY - p.tY);
    picks = [];
    for (const it of items) {
      const { s, tY } = it;
      const scrX = (RW / 2) * (1 + it.tX / tY);
      const hgt = f * 0.95 / tY, wid = hgt * (128 / 176);
      const left = scrX - wid / 2, topY = half + f * EYE / tY - hgt;
      const cx0 = Math.max(0, Math.floor(left)), cx1 = Math.min(RW - 1, Math.ceil(left + wid));
      if (cx1 < 0 || cx0 >= RW) continue;
      const im = spriteImage(s, colors);
      const fog = Math.min(1, Math.pow(tY / FOG_DIST, 1.15));
      const tn = s.at ? Wd.info(s.at.c, s.at.r).tone : null, lightK = tn ? tn.k : 0;
      ctx.globalAlpha = s.hidden ? 0.45 : 1;
      const bright = (1 - fog * 0.85) * (1 - lightK);
      if ('filter' in ctx) ctx.filter = bright < 0.98 ? `brightness(${bright.toFixed(2)})${tn && tn.tint ? ' hue-rotate(220deg) saturate(1.6)' : ''}` : 'none';
      let run = -1, any = false;
      const flush = end => {
        if (run < 0) return;
        const srcX = (run - left) / wid * im.width, srcW = (end - run) / wid * im.width;
        ctx.drawImage(im, srcX, 0, srcW, im.height, run * sx, topY * sy, (end - run) * sx, hgt * sy);
        run = -1;
      };
      for (let x = cx0; x <= cx1 + 1; x++) {
        const vis = x <= cx1 && x >= left && x < left + wid && tY < zbuf[x];
        if (vis && run < 0) run = x;
        if (!vis && run >= 0) { flush(x); any = true; }
      }
      if ('filter' in ctx) ctx.filter = 'none';
      ctx.globalAlpha = 1;
      const mid = Math.round(scrX);
      const centreSeen = mid >= 0 && mid < RW && tY < zbuf[mid];
      if (any) {
        picks.push({ s, x0: left * sx / dpr, x1: (left + wid) * sx / dpr, y0: topY * sy / dpr, y1: (topY + hgt) * sy / dpr, d: tY });
        if (s.label && tY < 9 && centreSeen) {
          ctx.font = `600 ${Math.round(Math.max(11, Math.min(18, 30 / tY)) * dpr)}px Rajdhani, sans-serif`;
          ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
          const tx = scrX * sx, ty = topY * sy - 2 * dpr, tw = ctx.measureText(s.label).width + 10 * dpr;
          ctx.fillStyle = 'rgba(0,0,0,.65)'; ctx.fillRect(tx - tw / 2, ty - 18 * dpr, tw, 18 * dpr);
          ctx.fillStyle = '#e8f6f4'; ctx.fillText(s.label, tx, ty - 2 * dpr);
        }
      }
    }

    // ---- HUD: scanlines, compass, crosshair
    ctx.globalAlpha = 0.12; ctx.fillStyle = '#000';
    for (let y = 0; y < H * dpr; y += 3 * dpr) ctx.fillRect(0, y, W * dpr, dpr);
    ctx.globalAlpha = 1;
    const names = G.hex ? null : ['E', 'S', 'W', 'N'];
    const deg = ((a * 180 / Math.PI) % 360 + 360) % 360;
    const label = G.hex ? `${Math.round((deg + 90) % 360)}°` : names[Math.round(deg / 90) % 4];
    ctx.font = `600 ${Math.round(14 * dpr)}px Rajdhani, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    const compass = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const heading = compass[Math.round(((deg + 90) % 360) / 45) % 8];
    ctx.fillStyle = 'rgba(0,0,0,.55)'; ctx.fillRect(W * dpr / 2 - 46 * dpr, 6 * dpr, 92 * dpr, 22 * dpr);
    ctx.fillStyle = colors.cellBorder || '#4fd8dc'; ctx.fillText(G.hex ? heading : label, W * dpr / 2, 9 * dpr);
    ctx.strokeStyle = 'rgba(255,255,255,.35)'; ctx.lineWidth = dpr;
    ctx.beginPath(); ctx.moveTo(W * dpr / 2 - 8 * dpr, H * dpr / 2); ctx.lineTo(W * dpr / 2 + 8 * dpr, H * dpr / 2);
    ctx.moveTo(W * dpr / 2, H * dpr / 2 - 8 * dpr); ctx.lineTo(W * dpr / 2, H * dpr / 2 + 8 * dpr); ctx.stroke();
    ctx.restore();
  }

  function pick(x, y) {
    let best = null;
    for (const p of picks) if (x >= p.x0 && x <= p.x1 && y >= p.y0 && y <= p.y1 && (!best || p.d < best.d)) best = p;
    return best ? best.s : null;
  }

  /* where the camera can step: square grids use the four edges, hex grids the six */
  function facingCount(map) { return map.gridType === 'hex' ? 6 : 4; }

  /* Camera, facing and controls shared by the player page and the GM's map screen.
     o = { map(): map, mapId(): id, at(): {c, r} | null (the cell the camera stands on),
           step(cell, dir): try to move there (returns nothing), door(edge): open/close a door on our cell,
           redraw(), storeKey: localStorage prefix } */
  function controller(o) {
    const st = { facing: 0, mapId: null, cam: null, from: null, to: null, t0: 0, dur: 0 };
    const dflt = () => (o.map() && o.map().gridType === 'hex' ? 4 : 0);      // face north
    const load = id => { try { const v = localStorage.getItem(o.storeKey + id); return v === null ? dflt() : +v || 0; } catch { return dflt(); } };
    const save = () => { try { localStorage.setItem(o.storeKey + st.mapId, String(st.facing)); } catch { /* private mode */ } };
    function target() {
      const map = o.map(), at = o.at(); if (!map || !at) return null;
      const p = geom(map).cellCenter(at.c, at.r);
      // stand at the back of the cell, looking across it, so the wall ahead is not in our face
      const a = angleOf(map, st.facing), back = geom(map).cs * (map.gridType === 'hex' ? 0.22 : 0.3);
      return { x: p.x - Math.cos(a) * back, y: p.y - Math.sin(a) * back, a };
    }
    function camera(now) {
      const id = o.mapId();
      if (id !== st.mapId) { st.mapId = id; st.facing = load(id); st.cam = null; }
      const t = target(); if (!t) return null;
      if (!st.cam) { st.cam = Object.assign({}, t); st.to = t; return { ...st.cam, animating: false }; }
      if (!st.to || st.to.x !== t.x || st.to.y !== t.y || st.to.a !== t.a) {
        // shortest turn
        let a0 = st.cam.a; while (t.a - a0 > Math.PI) a0 += 2 * Math.PI; while (a0 - t.a > Math.PI) a0 -= 2 * Math.PI;
        st.from = { x: st.cam.x, y: st.cam.y, a: a0 }; st.to = t; st.t0 = now;
        const far = Math.hypot(t.x - st.cam.x, t.y - st.cam.y) / geom(o.map()).cs;
        st.dur = far > 3 ? 0 : (far > 0.01 ? 190 : 150);
      }
      const k = st.dur ? Math.min(1, (now - st.t0) / st.dur) : 1, e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      const f = st.from || st.to;
      st.cam = { x: f.x + (st.to.x - f.x) * e, y: f.y + (st.to.y - f.y) * e, a: f.a + (st.to.a - f.a) * e };
      return { ...st.cam, animating: k < 1 };
    }
    function turn(d) { const n = facingCount(o.map()); st.facing = ((st.facing + d) % n + n) % n; save(); o.redraw(); }
    function ahead(back, sidestep) {
      const map = o.map(), at = o.at(); if (!map || !at) return null;
      const G = geom(map), n = facingCount(map);
      let e = st.facing;
      if (back) e = (e + n / 2) % n;
      if (sidestep) e = (e + sidestep + n) % n;
      return { cell: G.neighbor(at.c, at.r, e), edge: e };
    }
    function forward(back) { const a = ahead(back); if (a) o.step(a.cell, a.edge); }
    function strafe(d) { if (facingCount(o.map()) !== 4) return; const a = ahead(false, d); if (a) o.step(a.cell, a.edge); }
    function useDoor() { const a = ahead(false); if (a) o.door(a.edge); }
    function key(ev) {
      const k = ev.key.length === 1 ? ev.key.toLowerCase() : ev.key;
      if (k === 'ArrowUp' || k === 'w') forward(false);
      else if (k === 'ArrowDown' || k === 's') forward(true);
      else if (k === 'ArrowLeft' || k === 'a') turn(-1);
      else if (k === 'ArrowRight' || k === 'd') turn(1);
      else if (k === 'q') strafe(-1);
      else if (k === 'e') strafe(1);
      else if (k === 'Enter' || k === ' ') useDoor();
      else return false;
      ev.preventDefault();
      return true;
    }
    /* touch and mouse: the left and right thirds turn, the middle steps forward (upper half) or back */
    function tap(x, y, W, H) {
      if (x < W / 3) turn(-1);
      else if (x > 2 * W / 3) turn(1);
      else forward(y > H * 0.72);
    }
    return { camera, key, tap, turn, forward, useDoor, get facing() { return st.facing; } };
  }

  return { render, pick, angleOf, facingCount, controller };
})();
