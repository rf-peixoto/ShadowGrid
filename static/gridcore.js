/* GridCore: geometry + rendering shared by the GM editor and the player view. */
window.GridCore = (() => {
'use strict';
const SQRT3 = Math.sqrt(3);
const FONT = '"Rajdhani", "Barlow", sans-serif';

const MARKER_TYPES = [
  { id: 'poi',       name: 'Point of interest', shape: 'circle',   glyph: '?' },
  { id: 'loot',      name: 'Loot / item',       shape: 'diamond',  glyph: ''  },
  { id: 'danger',    name: 'Danger / enemy',    shape: 'triangle', glyph: '!' },
  { id: 'boss',      name: 'Boss / major foe',  shape: 'ring',     glyph: 'X' },
  { id: 'rest',      name: 'Rest / safe spot',  shape: 'square',   glyph: 'Z' },
  { id: 'shop',      name: 'Shop / vendor',     shape: 'square',   glyph: '$' },
  { id: 'exit',      name: 'Exit / stairs',     shape: 'chevron',  glyph: ''  },
  { id: 'link',      name: 'Portal / stairs',   shape: 'portal',   glyph: ''  },
  { id: 'key',       name: 'Key / unlock',      shape: 'circle',   glyph: 'K' },
  { id: 'npc',       name: 'NPC / contact',     shape: 'circle',   glyph: 'N' },
  { id: 'trap',      name: 'Trap / hazard',     shape: 'tridown',  glyph: 'T' },
  { id: 'objective', name: 'Objective',         shape: 'star',     glyph: ''  },
  { id: 'note',      name: 'Note',              shape: 'square',   glyph: 'i' },
];
const MARKER_BY_ID = Object.fromEntries(MARKER_TYPES.map(t => [t.id, t]));
const SQUARE_EDGES = ['North', 'East', 'South', 'West'];
const HEX_EDGES = ['South-east', 'South', 'South-west', 'North-west', 'North', 'North-east'];
const SQUARE_OFFSETS = [[0, -1], [1, 0], [0, 1], [-1, 0]];
const HEX_OFF_EVEN = [[1, 0], [0, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];
const HEX_OFF_ODD = [[1, 1], [0, 1], [-1, 1], [-1, 0], [0, -1], [1, 0]];

const key = (c, r) => `${c},${r}`;
function hexToRgb(hex) { const n = parseInt(hex.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
function mix(a, b, t) {
  const A = hexToRgb(a), B = hexToRgb(b);
  const m = A.map((v, i) => Math.round(v + (B[i] - v) * t));
  return `rgb(${m[0]},${m[1]},${m[2]})`;
}

// ---------------------------------------------------------------- geometry
function geom(map) {
  const hex = map.gridType === 'hex';
  const cs = map.cellSize;
  const R = cs / 2;
  const g = {
    hex, cs,
    edgeCount: hex ? 6 : 4,
    edgeNames: hex ? HEX_EDGES : SQUARE_EDGES,
    inBounds: (c, r) => c >= 0 && r >= 0 && c < map.width && r < map.height,
    mapPixelSize() {
      if (!hex) return { w: map.width * cs, h: map.height * cs };
      return { w: R * 1.5 * (map.width - 1) + 2 * R, h: R * SQRT3 * (map.height + 0.5) };
    },
    cellCenter(c, r) {
      if (!hex) return { x: (c + 0.5) * cs, y: (r + 0.5) * cs };
      return { x: R + R * 1.5 * c, y: R * SQRT3 / 2 + R * SQRT3 * (r + 0.5 * (c & 1)) };
    },
    cellCorners(c, r) {
      const { x, y } = g.cellCenter(c, r);
      if (!hex) { const h = cs / 2; return [{ x: x - h, y: y - h }, { x: x + h, y: y - h }, { x: x + h, y: y + h }, { x: x - h, y: y + h }]; }
      const pts = [];
      for (let i = 0; i < 6; i++) { const a = Math.PI / 3 * i; pts.push({ x: x + R * Math.cos(a), y: y + R * Math.sin(a) }); }
      return pts;
    },
    edgePoints(c, r, e) { const p = g.cellCorners(c, r); return [p[e], p[(e + 1) % p.length]]; },
    neighbor(c, r, e) {
      const off = hex ? ((c & 1) ? HEX_OFF_ODD : HEX_OFF_EVEN)[e] : SQUARE_OFFSETS[e];
      return { c: c + off[0], r: r + off[1] };
    },
    pointToCell(x, y) {
      if (!hex) { const c = Math.floor(x / cs), r = Math.floor(y / cs); return g.inBounds(c, r) ? { c, r } : null; }
      const px = x - R, py = y - R * SQRT3 / 2;
      const q = (2 / 3 * px) / R, rr = (-1 / 3 * px + SQRT3 / 3 * py) / R;
      let cx = q, cz = rr, cy = -cx - cz;
      let rx = Math.round(cx), ry = Math.round(cy), rz = Math.round(cz);
      const dx = Math.abs(rx - cx), dy = Math.abs(ry - cy), dz = Math.abs(rz - cz);
      if (dx > dy && dx > dz) rx = -ry - rz; else if (dy > dz) ry = -rx - rz; else rz = -rx - ry;
      const c = rx, r = rz + (rx - (rx & 1)) / 2;
      return g.inBounds(c, r) ? { c, r } : null;
    },
    nearestEdge(c, r, x, y) {
      let best = 0, bestD = Infinity;
      for (let e = 0; e < g.edgeCount; e++) {
        const [a, b] = g.edgePoints(c, r, e);
        const d = ((a.x + b.x) / 2 - x) ** 2 + ((a.y + b.y) / 2 - y) ** 2;
        if (d < bestD) { bestD = d; best = e; }
      }
      return best;
    },
    cellDistance(a, b) {
      if (!hex) return Math.max(Math.abs(a.c - b.c), Math.abs(a.r - b.r));
      const cube = p => { const x = p.c, z = p.r - (p.c - (p.c & 1)) / 2; return { x, y: -x - z, z }; };
      const A = cube(a), B = cube(b);
      return Math.max(Math.abs(A.x - B.x), Math.abs(A.y - B.y), Math.abs(A.z - B.z));
    },
    brushCells(center, size) {
      const out = [], rad = size - 1;
      for (let c = center.c - rad; c <= center.c + rad; c++)
        for (let r = center.r - rad - 1; r <= center.r + rad + 1; r++)
          if (g.inBounds(c, r) && g.cellDistance(center, { c, r }) <= rad) out.push({ c, r });
      return out;
    },
    centroid(keys) {
      let x = 0, y = 0, n = 0;
      for (const k of keys) { const [c, r] = k.split(',').map(Number); const p = g.cellCenter(c, r); x += p.x; y += p.y; n++; }
      return n ? { x: x / n, y: y / n } : null;
    },
  };
  return g;
}

// ---------------------------------------------------------------- drawing primitives
function tracePoly(g, pts, snap) {
  g.beginPath();
  pts.forEach((p, i) => { const x = snap ? Math.round(p.x) : p.x, y = snap ? Math.round(p.y) : p.y; i ? g.lineTo(x, y) : g.moveTo(x, y); });
  g.closePath();
}

function drawDoor(g, a, b, door, vis, pixel, size, col) {
  const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
  const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy);
  const ux = dx / len, uy = dy / len, half = len * 0.28;
  const base = door.color || col.doorDefault;
  g.lineCap = 'butt';
  g.lineWidth = Math.max(2, pixel ? Math.round(size / 6) : size / 6);
  g.strokeStyle = vis === 'dim' ? mix(base, col.revealedTint, 0.5) : base;
  const seg = (t0, t1) => { g.beginPath(); g.moveTo(Math.round(mx + ux * t0), Math.round(my + uy * t0)); g.lineTo(Math.round(mx + ux * t1), Math.round(my + uy * t1)); g.stroke(); };
  if (door.open) {
    seg(-half, -half * 0.35); seg(half * 0.35, half);
    g.strokeStyle = col.doorOpen; g.lineWidth = Math.max(1, g.lineWidth / 3); seg(-half * 0.3, half * 0.3);
  } else seg(-half, half);
  if (door.locked === true) {   // crossbar perpendicular to the door, in the door's own color
    const nx = -uy, ny = ux, bar = Math.max(4, size * 0.22);
    g.strokeStyle = vis === 'dim' ? mix(base, col.revealedTint, 0.5) : base; g.lineWidth = Math.max(2, size / 10); g.lineCap = 'round';
    g.beginPath(); g.moveTo(mx - nx * bar, my - ny * bar); g.lineTo(mx + nx * bar, my + ny * bar); g.stroke();
    g.lineCap = 'butt';
  }
}

function drawMarker(g, x, y, d, typeId, color, textColor, pixel) {
  const t = MARKER_BY_ID[typeId] || MARKER_TYPES[0];
  const h = d / 2, R = v => pixel ? Math.round(v) : v;
  g.fillStyle = color; g.strokeStyle = color; g.lineWidth = Math.max(1.5, d / 6);
  g.beginPath();
  switch (t.shape) {
    case 'circle': g.arc(R(x), R(y), R(h), 0, Math.PI * 2); g.fill(); break;
    case 'ring': g.arc(R(x), R(y), R(h), 0, Math.PI * 2); g.stroke(); g.beginPath(); g.arc(R(x), R(y), R(h * 0.55), 0, Math.PI * 2); g.fill(); break;
    case 'portal': g.arc(R(x), R(y), R(h), 0, Math.PI * 2); g.stroke(); g.beginPath(); g.arc(R(x), R(y), R(h * 0.6), 0, Math.PI * 2); g.stroke();
      g.beginPath(); g.arc(R(x), R(y), R(h * 0.22), 0, Math.PI * 2); g.fill(); break;
    case 'diamond': g.moveTo(R(x), R(y - h)); g.lineTo(R(x + h), R(y)); g.lineTo(R(x), R(y + h)); g.lineTo(R(x - h), R(y)); g.closePath(); g.fill(); break;
    case 'triangle': g.moveTo(R(x), R(y - h)); g.lineTo(R(x + h), R(y + h * 0.8)); g.lineTo(R(x - h), R(y + h * 0.8)); g.closePath(); g.fill(); break;
    case 'tridown': g.moveTo(R(x), R(y + h)); g.lineTo(R(x + h), R(y - h * 0.8)); g.lineTo(R(x - h), R(y - h * 0.8)); g.closePath(); g.fill(); break;
    case 'square': g.fillRect(R(x - h * 0.85), R(y - h * 0.85), R(h * 1.7), R(h * 1.7)); break;
    case 'chevron':
      g.moveTo(R(x), R(y - h)); g.lineTo(R(x + h), R(y)); g.lineTo(R(x + h * 0.45), R(y)); g.lineTo(R(x + h * 0.45), R(y + h));
      g.lineTo(R(x - h * 0.45), R(y + h)); g.lineTo(R(x - h * 0.45), R(y)); g.lineTo(R(x - h), R(y)); g.closePath(); g.fill(); break;
    case 'star':
      for (let i = 0; i < 10; i++) { const rr = i % 2 ? h * 0.45 : h, a = -Math.PI / 2 + i * Math.PI / 5; const px = x + rr * Math.cos(a), py = y + rr * Math.sin(a); i ? g.lineTo(R(px), R(py)) : g.moveTo(R(px), R(py)); }
      g.closePath(); g.fill(); break;
  }
  if (t.glyph) {
    g.fillStyle = textColor; g.font = `bold ${Math.round(d * 0.62)}px ${pixel ? 'monospace' : FONT}`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    const yOff = t.shape === 'triangle' ? h * 0.2 : t.shape === 'tridown' ? -h * 0.2 : 0;
    g.fillText(t.glyph, R(x), R(y + yOff + d * 0.04));
  }
}

/* Shadowrun condition monitor: {p, pm, s, sm, ov, grunt?, last?} -> status word.
   Grunts have one track; what hit them last decides between bleeding out and knocked out. */
function cmStatus(cm) {
  if (!cm) return 'OK';
  if (cm.status && !cm.grunt) return cm.status;
  if (cm.grunt) {
    if (cm.pm && cm.p >= cm.pm) return cm.last === 'S' ? 'Unconscious' : 'Dying';
    return cm.p ? 'Wounded' : 'OK';
  }
  if (cm.pm && cm.ov && cm.p >= cm.pm + cm.ov) return 'Dead';
  if (cm.pm && cm.p >= cm.pm) return 'Dying';
  if (cm.sm && cm.s >= cm.sm) return 'Unconscious';
  if ((cm.p || 0) + (cm.s || 0) > 0) return 'Wounded';
  return 'OK';
}
/* status effects (Prone, Burning…) drawn as a row of small icons above a token or marker */
const STATUS_ICONS = { Blinded: '👁', Burning: '🔥', Chilled: '❄', Confused: '❓', Corrosive: '🧪', Cover: '🛡', Dazed: '💫',
  Deafened: '🔇', Fatigued: '😩', Frightened: '😱', Hazed: '🌫', Hobbled: '🦶', Immobilized: '⛓', Invisible: '👻',
  Nauseated: '🤢', Panicked: '🏃', Petrified: '🗿', Poisoned: '☠', Prone: '⬇', Silent: '🤫', Stilled: '⏸', Wet: '💧', Zapped: '⚡' };
function drawStatuses(g, x, y, size, statuses) {
  const names = Object.keys(statuses || {});
  if (!names.length) return;
  const s = Math.max(9, size * 0.34), gap = s * 0.1, total = names.length * (s + gap) - gap;
  let cx = x - total / 2 + s / 2;
  g.font = `${Math.round(s * 0.78)}px ${FONT}`; g.textAlign = 'center'; g.textBaseline = 'middle';
  for (const n of names) {
    g.fillStyle = 'rgba(5,10,12,.82)'; g.beginPath(); g.arc(cx, y, s / 2, 0, Math.PI * 2); g.fill();
    g.strokeStyle = '#ff2f7d'; g.lineWidth = 1; g.stroke();
    g.fillStyle = '#fff'; g.fillText(STATUS_ICONS[n] || n.charAt(0), cx, y + s * 0.04);
    const v = statuses[n];
    if (v !== true && v > 1) { g.font = `bold ${Math.round(s * 0.42)}px ${FONT}`; g.fillStyle = '#ffd23f'; g.fillText(String(v), cx + s * 0.38, y + s * 0.34); g.font = `${Math.round(s * 0.78)}px ${FONT}`; }
    cx += s + gap;
  }
}
const STATUS_COLOR = { OK: '#6dff9c', Wounded: '#ffd23f', Unconscious: '#b98cff', Dying: '#ff4053', Dead: '#7f9b98' };
function drawCM(g, x, y, size, cm, pixel) {
  if (!cm || (!cm.pm && !cm.sm)) return;
  const R = v => pixel ? Math.round(v) : v;
  const w = size * 1.15, h = Math.max(2, size * 0.1), gap = Math.max(1, size * 0.03);
  const tracks = [];
  if (cm.pm) tracks.push([cm.p, cm.pm, '#ff4053']);
  if (cm.sm) tracks.push([cm.s, cm.sm, '#ffb02e']);
  const total = tracks.length * h + (tracks.length - 1) * gap;
  let ty = y - total / 2;
  g.fillStyle = 'rgba(0,0,0,.75)'; g.fillRect(R(x - w / 2 - gap), R(ty - gap), R(w + gap * 2), R(total + gap * 2));
  for (const [dmg, max, color] of tracks) {
    const left = Math.max(0, max - Math.min(dmg, max)) / max;
    g.fillStyle = '#1d3034'; g.fillRect(R(x - w / 2), R(ty), R(w), R(h));
    g.fillStyle = color; g.fillRect(R(x - w / 2), R(ty), R(w * left), R(h));
    ty += h + gap;
  }
  const st = cmStatus(cm);
  if (st !== 'OK' && st !== 'Wounded') {
    const text = st === 'Unconscious' ? 'KO' : st.toUpperCase();
    g.font = `bold ${Math.max(7, Math.round(size * 0.26))}px ${FONT}`; g.textAlign = 'center'; g.textBaseline = 'middle';
    const tw = g.measureText(text).width + 4, th = size * 0.3, by = y + total / 2 + gap + th / 2 + 1;
    g.fillStyle = 'rgba(0,0,0,.8)'; g.fillRect(R(x - tw / 2), R(by - th / 2), R(tw), R(th));
    g.fillStyle = STATUS_COLOR[st]; g.fillText(text, R(x), R(by + 1));
  }
}
function drawToken(g, x, y, d, tok, col, pixel) {
  const R = v => pixel ? Math.round(v) : v;
  const st = cmStatus(tok.cm);
  if (st === 'Dead' || st === 'Dying' || st === 'Unconscious') g.globalAlpha = 0.6;
  g.beginPath(); g.arc(R(x), R(y), R(d / 2), 0, Math.PI * 2);
  g.fillStyle = tok.color; g.fill();
  g.lineWidth = Math.max(1.5, d / 8); g.strokeStyle = tok.me ? col.tokenOutline : 'rgba(0,0,0,.6)'; g.stroke();
  g.fillStyle = '#111'; g.font = `bold ${Math.round(d * 0.55)}px ${pixel ? 'monospace' : FONT}`;
  g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillText((tok.name || '?').trim().charAt(0).toUpperCase(), R(x), R(y + d * 0.04));
  g.globalAlpha = 1;
  drawCM(g, x, y + d * 0.72, d, tok.cm, pixel);
  if (tok.statuses) drawStatuses(g, x, y - d * 0.78, d, tok.statuses);
}

// ---------------------------------------------------------------- scene
/* view = { mode: 'edit'|'gm'|'player', explored: Set|null, mapStation: bool,
            tokens: [{c,r,color,name,me}], hoverLabel: {c,r,text}|null, rooms: bool } */
function visibility(view, k, cell) {
  if (view.mode !== 'player') return 'full';
  if (!cell) return 'hidden';
  if (view.explored && view.explored.has(k)) return 'full';
  if (view.mapStation && !cell.secret) return 'dim';
  return 'hidden';
}

function drawGrid(g, map, opts) {
  const showGrid = opts.grid === undefined ? map.settings.showGrid : opts.grid;
  if (!showGrid) return;
  const G = geom(map), col = map.settings.colors, snap = opts.pixel, size = G.cs, { w, h } = G.mapPixelSize();
  g.strokeStyle = col.grid; g.lineWidth = 1;
  if (!G.hex) {
    g.beginPath();
    for (let c = 0; c <= map.width; c++) { const x = snap ? Math.round(c * size) + 0.5 : c * size; g.moveTo(x, 0); g.lineTo(x, h); }
    for (let r = 0; r <= map.height; r++) { const y = snap ? Math.round(r * size) + 0.5 : r * size; g.moveTo(0, y); g.lineTo(w, y); }
    g.stroke();
  } else {
    g.beginPath();
    for (let c = 0; c < map.width; c++) for (let r = 0; r < map.height; r++) {
      const p = G.cellCorners(c, r);
      p.forEach((pt, i) => { const x = snap ? Math.round(pt.x) : pt.x, y = snap ? Math.round(pt.y) : pt.y; i ? g.lineTo(x, y) : g.moveTo(x, y); });
      g.closePath();
    }
    g.stroke();
  }
}

function renderScene(g, map, view, opts) {
  const { pixel, forExport } = opts;
  const G = geom(map), col = map.settings.colors, snap = pixel, size = G.cs;
  const cells = map.data.cells, { w, h } = G.mapPixelSize();
  g.imageSmoothingEnabled = !pixel; g.lineJoin = 'miter';
  if (opts.background !== false) {
    g.fillStyle = view.mode === 'edit' ? col.background : col.fog;
    g.fillRect(0, 0, Math.ceil(w), Math.ceil(h));
  }
  drawGrid(g, map, opts);
  if (opts.onlyGrid) return;
  // light: the player's cells carry it (sources included); the GM's view works it out (view.light)
  const amb = view.mode === 'player' ? 0 : Math.max(0, LIGHT_LEVELS.indexOf((map.settings && map.settings.ambientLight) || 'bright'));
  const lightOf = view.light || ((c, r, cell) => cell.light ? Math.max(0, LIGHT_LEVELS.indexOf(cell.light)) : amb);
  const smokeCells = [];

  for (const k in cells) {
    const cell = cells[k]; if (!cell) continue;
    const [c, r] = k.split(',').map(Number);
    if (!G.inBounds(c, r)) continue;
    const vis = visibility(view, k, cell);
    if (vis === 'hidden') continue;
    const corners = G.cellCorners(c, r);
    if (cell.fill) {
      let fill = cell.fill;
      if (vis === 'dim') fill = mix(cell.fill, col.revealedTint, 0.65);
      else if (view.mode === 'player') fill = mix(cell.fill, col.exploredTint, 0.10);
      const lv = lightOf(c, r, cell);
      if (lv) fill = mix(fill, '#000000', (view.mode === 'player' ? [0, 0.42, 0.74] : [0, 0.3, 0.56])[lv]);
      tracePoly(g, corners, snap); g.fillStyle = fill; g.fill();
      if (cell.borderOn !== false && opts.borders !== false) {
        const b = cell.border || col.cellBorder;
        g.strokeStyle = vis === 'dim' ? mix(b, col.revealedTint, 0.5) : b;
        g.lineWidth = Math.max(1, pixel ? Math.round(size / 16) : size / 16); g.stroke();
      }
      if (cell.smoke) smokeCells.push({ c, r, kind: cell.smoke });
    }
    if (cell.secret && view.mode === 'edit') {
      g.save(); tracePoly(g, corners, snap); g.clip();
      g.strokeStyle = col.secretHatch; g.lineWidth = pixel ? 1 : 1.2;
      const cx = corners.reduce((s, p) => s + p.x, 0) / corners.length, cy = corners.reduce((s, p) => s + p.y, 0) / corners.length;
      const step = Math.max(3, Math.round(size / 6));
      for (let d = -size; d <= size; d += step) { g.beginPath(); g.moveTo(cx - size + d, cy - size); g.lineTo(cx + size + d, cy + size); g.stroke(); }
      g.restore();
    }
  }

  if (smokeCells.length) drawSmokeLayer(g, G, smokeCells, size, cells);

  const rank = { hidden: 0, dim: 1, full: 2 };
  for (const k in cells) {
    const cell = cells[k]; if (!cell || !cell.doors) continue;
    const [c, r] = k.split(',').map(Number);
    if (!G.inBounds(c, r)) continue;
    const visA = visibility(view, k, cell);
    for (const e in cell.doors) {
      // a door is visible from either side of the wall
      const n = G.neighbor(c, r, +e), nk = key(n.c, n.r);
      const visB = G.inBounds(n.c, n.r) ? visibility(view, nk, cells[nk]) : 'hidden';
      const vis = rank[visA] >= rank[visB] ? visA : visB;
      if (vis === 'hidden') continue;
      const [a, b] = G.edgePoints(c, r, +e); drawDoor(g, a, b, cell.doors[e], vis, pixel, size, col);
    }
  }

  if (opts.sprites === false) return;
  if (view.rooms && map.data.rooms && opts.roomNames !== false) {
    g.fillStyle = col.roomLabel; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.font = `${pixel ? 'bold ' : ''}${Math.max(8, Math.round(size * 0.34))}px ${pixel ? 'monospace' : FONT}`;
    for (const room of map.data.rooms) {
      const ctr = G.centroid(room.cells);
      if (ctr) g.fillText(room.name, Math.round(ctr.x), Math.round(ctr.y));
    }
  }

  for (const m of map.data.markers) {
    if (!G.inBounds(m.c, m.r)) continue;
    if (visibility(view, key(m.c, m.r), cells[key(m.c, m.r)]) !== 'full') continue;
    if (m.hidden && view.mode === 'player') continue;
    const { x, y } = G.cellCenter(m.c, m.r);
    if (m.hidden) g.globalAlpha = 0.45;
    drawMarker(g, x, y, size * 0.62, m.type, m.color || col.markerDefault, col.markerText, pixel);
    if (m.cm) drawCM(g, x, y + size * 0.45, size * 0.62, m.cm, pixel);
    if (m.statuses) drawStatuses(g, x, y - size * 0.5, size * 0.62, m.statuses);
    if (m.hidden) {
      g.globalAlpha = 1; g.strokeStyle = col.highlight; g.lineWidth = Math.max(1, size / 20); g.setLineDash([3, 2]);
      g.beginPath(); g.arc(Math.round(x), Math.round(y), size * 0.4, 0, Math.PI * 2); g.stroke(); g.setLineDash([]);
    }
  }

  for (const t of (view.tokens || [])) {
    if (!G.inBounds(t.c, t.r)) continue;
    if (view.mode === 'player' && visibility(view, key(t.c, t.r), cells[key(t.c, t.r)]) !== 'full') continue;
    const { x, y } = G.cellCenter(t.c, t.r);
    drawToken(g, x, y, size * 0.7, t, col, pixel);
  }

  if (!forExport && view.hoverLabel && view.hoverLabel.text) {
    const { x, y } = G.cellCenter(view.hoverLabel.c, view.hoverLabel.r);
    g.font = `${pixel ? 'bold ' : ''}${Math.max(9, Math.round(size * 0.38))}px ${pixel ? 'monospace' : FONT}`;
    g.textAlign = 'center'; g.textBaseline = 'top';
    const tw = g.measureText(view.hoverLabel.text).width + 8;
    g.fillStyle = 'rgba(0,0,0,.78)';
    g.fillRect(Math.round(x - tw / 2), Math.round(y + size * 0.4), Math.round(tw), Math.round(size * 0.45));
    g.fillStyle = '#fff'; g.fillText(view.hoverLabel.text, Math.round(x), Math.round(y + size * 0.42));
  }
}

// ---------------------------------------------------------------- iso sprites (drawn upright in screen space)
/* In the isometric view the floor is drawn through the projection, but anything with text or a
   silhouette (tokens, markers, room names, labels) is drawn upright at its projected position,
   SNES-style, with a ground shadow. `vp` is the viewport; `g` has a plain dpr transform. */
function shadow(g, x, y, d) {
  g.fillStyle = 'rgba(0,0,0,.45)';
  g.beginPath(); g.ellipse(x, y, d * 0.42, d * 0.16, 0, 0, Math.PI * 2); g.fill();
}
function renderSprites(g, map, view, vp, opts = {}) {
  const G = geom(map), col = map.settings.colors, cells = map.data.cells;
  const z = vp.zoom, size = G.cs * z, items = [];
  for (const m of map.data.markers) {
    if (!G.inBounds(m.c, m.r)) continue;
    if (visibility(view, key(m.c, m.r), cells[key(m.c, m.r)]) !== 'full') continue;
    if (m.hidden && view.mode === 'player') continue;
    const c = G.cellCenter(m.c, m.r), p = vp.toScreen(c.x, c.y);
    items.push({ y: p.y, draw: () => {
      const d = size * 0.62, lift = d * 0.55;
      shadow(g, p.x, p.y, d);
      if (m.hidden) g.globalAlpha = 0.45;
      drawMarker(g, p.x, p.y - lift, d, m.type, m.color || col.markerDefault, col.markerText, false);
      g.globalAlpha = 1;
      if (m.hidden) { g.strokeStyle = col.highlight; g.lineWidth = 1.5; g.setLineDash([3, 2]); g.beginPath(); g.arc(p.x, p.y - lift, d * 0.66, 0, Math.PI * 2); g.stroke(); g.setLineDash([]); }
      if (m.cm) drawCM(g, p.x, p.y - lift - d * 0.85, d, m.cm, false);
      if (m.statuses) drawStatuses(g, p.x, p.y - lift - d * (m.cm ? 1.25 : 0.95), d, m.statuses);
    } });
  }
  for (const t of (view.tokens || [])) {
    if (!G.inBounds(t.c, t.r)) continue;
    if (view.mode === 'player' && visibility(view, key(t.c, t.r), cells[key(t.c, t.r)]) !== 'full') continue;
    if (opts.skipToken && opts.skipToken(t)) continue;
    const c = G.cellCenter(t.c, t.r), p = vp.toScreen(c.x, c.y);
    items.push({ y: p.y + 0.1, draw: () => drawTokenSprite(g, p.x, p.y, size * 0.7, t, col) });
  }
  items.sort((a, b) => a.y - b.y);
  if (view.rooms && map.data.rooms && opts.roomNames !== false) {
    g.fillStyle = col.roomLabel; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.font = `600 ${Math.max(10, Math.round(size * 0.34))}px ${FONT}`;
    for (const room of map.data.rooms) {
      const ctr = G.centroid(room.cells); if (!ctr) continue;
      const p = vp.toScreen(ctr.x, ctr.y);
      g.fillText(room.name.toUpperCase(), p.x, p.y);
    }
  }
  for (const it of items) it.draw();
}
/* Which marker or token is drawn under a screen point? In the isometric view sprites stand above
   their cell, so a click on the drawn icon lands on another cell; this finds the sprite itself.
   Front-most (lowest on screen) first. Returns {kind: 'marker', m} | {kind: 'token', t} | null. */
function pickSprite(map, view, vp, sx, sy) {
  if (!vp.iso || !map) return null;
  const G = geom(map), cells = map.data.cells, size = G.cs * vp.zoom, hits = [];
  const test = (c, r, d, liftK) => {
    const ctr = G.cellCenter(c, r), p = vp.toScreen(ctr.x, ctr.y), lift = d * liftK, rad = d * 0.62;
    const dx = sx - p.x, dy = sy - (p.y - lift);
    // the icon disc, or the stand down to its cell
    if (dx * dx + dy * dy <= rad * rad || (Math.abs(dx) <= d * 0.25 && sy <= p.y + d * 0.2 && sy >= p.y - lift)) return p.y;
    return null;
  };
  for (const m of map.data.markers || []) {
    if (!G.inBounds(m.c, m.r)) continue;
    if (visibility(view, key(m.c, m.r), cells[key(m.c, m.r)]) !== 'full') continue;
    if (m.hidden && view.mode === 'player') continue;
    const y = test(m.c, m.r, size * 0.62, 0.55);
    if (y !== null) hits.push({ y, hit: { kind: 'marker', m } });
  }
  for (const t of view.tokens || []) {
    if (!G.inBounds(t.c, t.r)) continue;
    if (view.mode === 'player' && visibility(view, key(t.c, t.r), cells[key(t.c, t.r)]) !== 'full') continue;
    const y = test(t.c, t.r, size * 0.7, 0.62);
    if (y !== null) hits.push({ y: y + 0.1, hit: { kind: 'token', t } });
  }
  hits.sort((a, b) => b.y - a.y);
  return hits.length ? hits[0].hit : null;
}
function drawTokenSprite(g, x, y, d, tok, col) {
  const lift = d * 0.62;
  shadow(g, x, y, d);
  // a small "stand" between the ground and the token, like a miniature
  g.strokeStyle = 'rgba(0,0,0,.5)'; g.lineWidth = Math.max(1, d / 12);
  g.beginPath(); g.moveTo(x, y); g.lineTo(x, y - lift); g.stroke();
  drawToken(g, x, y - lift, d, Object.assign({}, tok, { cm: null, statuses: null }), col, false);
  if (tok.cm) drawCM(g, x, y - lift - d * 0.85, d, tok.cm, false);
  if (tok.statuses) drawStatuses(g, x, y - lift - d * (tok.cm ? 1.25 : 0.95), d, tok.statuses);
}
/* screen-space label box (hover text) */
function drawLabel(g, x, y, text, size) {
  g.font = `600 ${Math.max(11, Math.round(size * 0.38))}px ${FONT}`; g.textAlign = 'center'; g.textBaseline = 'top';
  const tw = g.measureText(text).width + 10, th = Math.max(16, size * 0.5);
  g.fillStyle = 'rgba(5,10,12,.88)'; g.fillRect(x - tw / 2, y, tw, th);
  g.fillStyle = '#e6f1ef'; g.fillText(text, x, y + (th - Math.max(11, size * 0.38)) / 2);
}

// ---------------------------------------------------------------- pings & bounds
function drawPing(g, x, y, size, color, age) {   // age in seconds, animates for ~8s
  const t = (age % 1.6) / 1.6;
  g.strokeStyle = color; g.globalAlpha = Math.max(0, 1 - t) * Math.max(0.2, 1 - age / 9);
  g.lineWidth = Math.max(2, size / 8);
  g.beginPath(); g.arc(x, y, size * (0.25 + t * 0.9), 0, Math.PI * 2); g.stroke();
  g.globalAlpha = Math.max(0.2, 1 - age / 9);
  g.fillStyle = color; g.beginPath(); g.arc(x, y, size * 0.12, 0, Math.PI * 2); g.fill();
  g.globalAlpha = 1;
}
function paintedBounds(map, margin = 1) {   // pixel rectangle around painted cells
  const G = geom(map); let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const k in map.data.cells) {
    const cell = map.data.cells[k]; if (!cell || !cell.fill) continue;
    const [c, r] = k.split(',').map(Number); if (!G.inBounds(c, r)) continue;
    for (const p of G.cellCorners(c, r)) { minX = Math.min(minX, p.x); minY = Math.min(minY, p.y); maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y); }
  }
  const { w, h } = G.mapPixelSize();
  if (minX === Infinity) return { x: 0, y: 0, w, h };
  const m = margin * G.cs;
  const x = Math.max(0, minX - m), y = Math.max(0, minY - m);
  return { x, y, w: Math.min(w, maxX + m) - x, h: Math.min(h, maxY + m) - y };
}

// ---------------------------------------------------------------- movement helpers (mirror of geometry.py)
function doorOnEdge(G, cells, c, r, e) {
  const own = ((cells[key(c, r)] || {}).doors || {})[e];
  if (own) return own;
  const n = G.neighbor(c, r, e), opp = G.hex ? (e + 3) % 6 : (e + 2) % 4;
  return ((cells[key(n.c, n.r)] || {}).doors || {})[opp] || null;
}
function passable(G, cells, a, b) {
  const cell = cells[key(b.c, b.r)];
  if (!G.inBounds(b.c, b.r) || !cell || !cell.fill) return false;
  for (let e = 0; e < G.edgeCount; e++) {
    const n = G.neighbor(a.c, a.r, e);
    if (n.c === b.c && n.r === b.r) { const d = doorOnEdge(G, cells, a.c, a.r, e); return !(d && !d.open); }
  }
  return false;
}
function findPath(G, cells, start, goal, maxLen = 120) {
  if (start.c === goal.c && start.r === goal.r) return [];
  const sk = key(start.c, start.r), prev = new Map([[sk, null]]);
  let frontier = [start], depth = 0;
  while (frontier.length && depth < maxLen) {
    const next = [];
    for (const cur of frontier) for (let e = 0; e < G.edgeCount; e++) {
      const nb = G.neighbor(cur.c, cur.r, e), nk = key(nb.c, nb.r);
      if (prev.has(nk) || !passable(G, cells, cur, nb)) continue;
      prev.set(nk, cur);
      if (nb.c === goal.c && nb.r === goal.r) {
        const path = []; let p = nb;
        while (p && key(p.c, p.r) !== sk) { path.push(p); p = prev.get(key(p.c, p.r)); }
        return path.reverse();
      }
      next.push(nb);
    }
    frontier = next; depth++;
  }
  return null;
}

// ---------------------------------------------------------------- viewport helper (zoom/pan/projection/minimap)
/* screen = zoom * M * world + pan, where M is identity (flat, top-down) or the isometric
   projection: rotate 45 degrees, then squash vertically (SNES Shadowrun style). */
const ISO_ANGLE = Math.PI / 4, ISO_SQUASH = 0.58;
function makeViewport(canvas, wrap, minimapCanvas, getMap) {
  const vp = { zoom: 1, panX: 0, panY: 0, iso: false, m: [1, 0, 0, 1] };
  const apply = (x, y) => ({ u: vp.m[0] * x + vp.m[2] * y, v: vp.m[1] * x + vp.m[3] * y });
  vp.toScreen = (x, y) => { const { u, v } = apply(x, y); return { x: u * vp.zoom + vp.panX, y: v * vp.zoom + vp.panY }; };
  vp.screenToMap = (sx, sy) => {
    const u = (sx - vp.panX) / vp.zoom, v = (sy - vp.panY) / vp.zoom, [a, b, c, d] = vp.m, det = a * d - b * c;
    return { x: (d * u - c * v) / det, y: (-b * u + a * v) / det };
  };
  vp.matrix = dpr => [dpr * vp.zoom * vp.m[0], dpr * vp.zoom * vp.m[1], dpr * vp.zoom * vp.m[2], dpr * vp.zoom * vp.m[3], Math.round(vp.panX * dpr), Math.round(vp.panY * dpr)];
  vp.canvasPoint = ev => { const b = canvas.getBoundingClientRect(); return { sx: ev.clientX - b.left, sy: ev.clientY - b.top }; };
  function bounds() {
    const { w, h } = geom(getMap()).mapPixelSize();
    const pts = [apply(0, 0), apply(w, 0), apply(0, h), apply(w, h)];
    return { minU: Math.min(...pts.map(p => p.u)), maxU: Math.max(...pts.map(p => p.u)), minV: Math.min(...pts.map(p => p.v)), maxV: Math.max(...pts.map(p => p.v)) };
  }
  vp.fit = () => {
    const B = bounds(), W = wrap.clientWidth, H = wrap.clientHeight, bw = B.maxU - B.minU, bh = B.maxV - B.minV;
    vp.zoom = Math.max(0.05, Math.min((W - 40) / bw, (H - 40) / bh));
    vp.panX = (W - bw * vp.zoom) / 2 - B.minU * vp.zoom; vp.panY = (H - bh * vp.zoom) / 2 - B.minV * vp.zoom;
  };
  vp.zoomAt = (sx, sy, factor) => {
    const m = vp.screenToMap(sx, sy);
    vp.zoom = Math.min(12, Math.max(0.05, vp.zoom * factor));
    const { u, v } = apply(m.x, m.y);
    vp.panX = sx - u * vp.zoom; vp.panY = sy - v * vp.zoom;
  };
  vp.centerOn = (x, y) => { const { u, v } = apply(x, y); vp.panX = wrap.clientWidth / 2 - u * vp.zoom; vp.panY = wrap.clientHeight / 2 - v * vp.zoom; };
  vp.setIso = on => {
    const W = wrap.clientWidth, H = wrap.clientHeight, centre = vp.screenToMap(W / 2, H / 2);
    vp.iso = !!on;
    vp.m = on ? [Math.cos(ISO_ANGLE), ISO_SQUASH * Math.sin(ISO_ANGLE), -Math.sin(ISO_ANGLE), ISO_SQUASH * Math.cos(ISO_ANGLE)] : [1, 0, 0, 1];
    if (W && H && isFinite(centre.x)) vp.centerOn(centre.x, centre.y);
  };
  vp.minimapSize = () => {
    const map = getMap(); const { w, h } = geom(map).mapPixelSize();
    const MW = 180, MH = Math.max(40, Math.round(MW * h / w));
    return { MW, MH, scale: MW / w };
  };
  vp.drawMinimap = (miniScene) => {
    if (!minimapCanvas) return;
    const map = getMap(); if (!map) return;
    const { w } = geom(map).mapPixelSize();
    const { MW, MH } = vp.minimapSize();
    const dpr = window.devicePixelRatio || 1;
    if (minimapCanvas.width !== MW * dpr || minimapCanvas.height !== MH * dpr) { minimapCanvas.width = MW * dpr; minimapCanvas.height = MH * dpr; minimapCanvas.style.width = MW + 'px'; minimapCanvas.style.height = MH + 'px'; }
    const g = minimapCanvas.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, MW, MH);
    g.imageSmoothingEnabled = true;
    g.drawImage(miniScene, 0, 0, MW, MH);
    const s = MW / w, W = wrap.clientWidth, H = wrap.clientHeight;
    // the visible screen area, mapped back onto the (top-down) minimap; a diamond in the iso view
    const q = [[0, 0], [W, 0], [W, H], [0, H]].map(([x, y]) => vp.screenToMap(x, y));
    g.save(); g.beginPath(); g.rect(0, 0, MW, MH); g.clip();
    g.strokeStyle = 'rgba(255,255,255,.9)'; g.lineWidth = 1.5;
    g.beginPath(); q.forEach((p, i) => i ? g.lineTo(p.x * s, p.y * s) : g.moveTo(p.x * s, p.y * s)); g.closePath(); g.stroke();
    g.restore();
    vp._mmScale = s;
  };
  if (minimapCanvas) {
    let down = false;
    const jump = ev => {
      const b = minimapCanvas.getBoundingClientRect();
      const s = vp._mmScale || 1;
      vp.centerOn((ev.clientX - b.left) / s, (ev.clientY - b.top) / s);
      minimapCanvas.dispatchEvent(new CustomEvent('minimap-move'));
    };
    minimapCanvas.addEventListener('pointerdown', ev => { down = true; minimapCanvas.setPointerCapture(ev.pointerId); jump(ev); });
    minimapCanvas.addEventListener('pointermove', ev => { if (down) jump(ev); });
    minimapCanvas.addEventListener('pointerup', () => { down = false; });
  }
  return vp;
}

/* Isometric frame: cached layers -> main canvas. layers = { grid, floor, sides } canvases in map space
   with scale q. Draws the grid, then the floor "slab" sides (a darkened copy of the floor stacked
   downwards), then the floor itself, all through the projection. */
function buildIsoLayers(L, map, view, q) {
  const G = geom(map), { w, h } = G.mapPixelSize(), ow = Math.ceil(w * q), oh = Math.ceil(h * q);
  for (const k of ['grid', 'floor', 'sides']) {
    if (!L[k]) L[k] = document.createElement('canvas');
    if (L[k].width !== ow || L[k].height !== oh) { L[k].width = ow; L[k].height = oh; }
  }
  const gg = L.grid.getContext('2d'); gg.setTransform(q, 0, 0, q, 0, 0); gg.clearRect(0, 0, w, h);
  renderScene(gg, map, view, { background: false, onlyGrid: true });
  const fg = L.floor.getContext('2d'); fg.setTransform(q, 0, 0, q, 0, 0); fg.clearRect(0, 0, w, h);
  renderScene(fg, map, view, { background: false, grid: false, sprites: false });
  const sg = L.sides.getContext('2d'); sg.setTransform(1, 0, 0, 1, 0, 0); sg.globalCompositeOperation = 'source-over';
  sg.clearRect(0, 0, ow, oh); sg.drawImage(L.floor, 0, 0);
  sg.globalCompositeOperation = 'source-atop'; sg.fillStyle = 'rgba(0,0,0,.62)'; sg.fillRect(0, 0, ow, oh);
  sg.globalCompositeOperation = 'source-over';
  L.q = q;
}
function drawIsoLayers(ctx, L, vp, dpr, cs) {
  const M = vp.matrix(dpr), q = L.q || 1, wq = L.floor.width / q, hq = L.floor.height / q;
  ctx.setTransform(...M); ctx.drawImage(L.grid, 0, 0, wq, hq);
  const depth = Math.max(2, cs * vp.zoom * 0.3) * dpr, steps = Math.min(10, Math.ceil(depth / 1.5));
  for (let i = steps; i >= 1; i--) { const off = depth * i / steps; ctx.setTransform(M[0], M[1], M[2], M[3], M[4], M[5] + off); ctx.drawImage(L.sides, 0, 0, wq, hq); }
  ctx.setTransform(...M); ctx.drawImage(L.floor, 0, 0, wq, hq);
}

// ---------------------------------------------------------------- line of sight, light and vision (SightCore)
/* The rules live in sightcore.js (the same as the server's geometry.py). Here: a light-weight copy of the map
   for it, a cache, and a Web Worker so big maps and hexes don't stall drawing. */
const LIGHT_LEVELS = ['bright', 'dim', 'dark'];
/* light sources on a map seen by the GM: lit markers and flashlights of runners standing on it.
   players: [{c, r, flashlight}] (tokens). Radii in cells. */
function lightSources(map, players) {
  const cm = (map.settings && map.settings.cellMeters) || 2, out = [];
  for (const m of map.data.markers || []) if (m.light) out.push([m.c, m.r, Math.max(0, Math.ceil(m.light / cm - 1e-9))]);
  for (const p of players || []) if (p.flashlight) out.push([p.c, p.r, Math.max(0, Math.ceil(10 / cm - 1e-9))]);
  return out;
}
/* the map as SightCore wants it. opts: { ambient, sources } (players' maps carry the light already) */
function sightMap(map, opts) {
  opts = opts || {};
  return { gridType: map.gridType, width: map.width, height: map.height, cells: map.data.cells,
           ambient: opts.ambient || 'bright', sources: opts.sources || [], cellM: (map.settings && map.settings.cellMeters) || 2 };
}
const worlds = { sig: null, w: null };
function sightWorld(map, opts, sig) {
  if (sig !== undefined && worlds.sig === sig && worlds.w) return worlds.w;
  const w = SightCore.world(sightMap(map, opts));
  if (sig !== undefined) { worlds.sig = sig; worlds.w = w; }
  return w;
}
/* sight and cover between two cells {c, r} (walls and closed doors) */
function lineOfSight(map, a, b) { return SightCore.world(sightMap(map)).cover([a.c, a.r], [b.c, b.r]); }

const fieldCache = new Map();      // key -> field (a few recent ones)
const SW = { worker: null, failed: false, mapSig: null, pending: new Map(), seq: 0 };
function sightWorker() {
  if (SW.worker || SW.failed || typeof Worker === 'undefined') return SW.worker;
  try {
    const core = document.querySelector('script[src*="sightcore.js"]');
    if (!core) { SW.failed = true; return null; }
    const url = new URL('sightworker.js', core.src); url.search = '?c=' + encodeURIComponent(core.src);
    SW.worker = new Worker(url.href);
    SW.worker.onmessage = ev => {
      const m = ev.data || {}, cbs = SW.pending.get(m.key) || [];
      SW.pending.delete(m.key);
      if (m.error || !m.field) return;
      const f = m.field;
      remember(m.key, { from: f.from, radius: f.radius, seen: new Map(f.seen), hidden: new Set(f.hidden), dark: new Set(f.dark),
                        far: new Set(f.far), blind: new Map(f.blind) });
      for (const cb of cbs) try { cb(); } catch { /* ignore */ }
    };
    SW.worker.onerror = () => { SW.failed = true; SW.worker = null; SW.pending.clear(); };
  } catch { SW.failed = true; SW.worker = null; }
  return SW.worker;
}
function remember(k, f) { fieldCache.delete(k); fieldCache.set(k, f); while (fieldCache.size > 12) fieldCache.delete(fieldCache.keys().next().value); }
/* everything a viewer standing on `from` can see within `radius` steps (see SightCore.field). `sig` names the
   map version (change it when walls, doors, light or smoke change). opts: { vision, blinded, ambient, sources }.
   With onReady, the work runs in a worker: the call returns the last field for this map and viewer (or null)
   and onReady fires when the new one is in. Without it, it is worked out right away. */
function sightField(map, from, radius, sig, opts, onReady) {
  opts = opts || {};
  const eyes = Array.isArray(opts.vision) ? opts.vision.join('+') : '-';
  const base = `${sig}|${map.id}|${radius}|${eyes}|${opts.blinded || 0}|${JSON.stringify(opts.sources || [])}|${opts.ambient || ''}`;
  const k = `${base}|${from.c},${from.r}`;
  if (fieldCache.has(k)) return fieldCache.get(k);
  const w = onReady ? sightWorker() : null;
  if (!w) {
    const f = SightCore.field(sightWorld(map, opts, `${sig}|${map.id}|${JSON.stringify(opts.sources || [])}|${opts.ambient || ''}`), from, radius,
                              { vision: opts.vision, blinded: opts.blinded });
    remember(k, f);
    return f;
  }
  const mapSig = `${sig}|${map.id}|${JSON.stringify(opts.sources || [])}|${opts.ambient || ''}`;
  if (SW.mapSig !== mapSig) { w.postMessage({ type: 'map', sig: mapSig, map: sightMap(map, opts) }); SW.mapSig = mapSig; }
  if (!SW.pending.has(k)) {
    SW.pending.set(k, []);
    w.postMessage({ type: 'field', id: ++SW.seq, key: k, sig: mapSig, from: { c: from.c, r: from.r }, radius, opts: { vision: opts.vision, blinded: opts.blinded } });
  }
  SW.pending.get(k).push(onReady);
  // meanwhile: the most recent field with the same map and eyes (the viewer was probably one step away)
  let last = null;
  for (const [kk, f] of fieldCache) if (kk.startsWith(base + '|')) last = f;
  return last;
}
const COVER_NAMES = ['', 'I', 'II', 'III', 'IV'];
/* draw a sight field in map space (the caller sets the viewport transform) */
/* Smoke: one soft cloud over all the smoky cells, so neighbours flow into each other. Each cell adds a
   radial puff to a mask (dense in the middle, fading at the edge); the mask is then filled with a drifting
   noise texture and laid over the floor. Thermal smoke has a warm tint. */
const SMOKE_TONES = { smoke: [196, 206, 210], thermal: [226, 182, 152] };
const smokeTex = {};
function smokeTexture(kind) {
  if (smokeTex[kind]) return smokeTex[kind];
  const N = 160, cv = document.createElement('canvas'); cv.width = cv.height = N;
  const g = cv.getContext('2d'), img = g.createImageData(N, N), [R, Gc, B] = SMOKE_TONES[kind] || SMOKE_TONES.smoke;
  // tileable value noise, three octaves
  const grid = (n, seed) => { const a = []; let x = seed; for (let i = 0; i < n * n; i++) { x = (x * 1103515245 + 12345) & 0x7fffffff; a.push(x / 0x7fffffff); } return a; };
  const octs = [[5, 0.55, grid(5, 7)], [10, 0.3, grid(10, 19)], [20, 0.15, grid(20, 31)]];
  const smooth = t => t * t * (3 - 2 * t);
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    let v = 0;
    for (const [n, w, a] of octs) {
      const fx = x / N * n, fy = y / N * n, x0 = Math.floor(fx), y0 = Math.floor(fy), tx = smooth(fx - x0), ty = smooth(fy - y0);
      const at = (i, j) => a[((j % n) + n) % n * n + ((i % n) + n) % n];
      const top = at(x0, y0) + (at(x0 + 1, y0) - at(x0, y0)) * tx, bot = at(x0, y0 + 1) + (at(x0 + 1, y0 + 1) - at(x0, y0 + 1)) * tx;
      v += (top + (bot - top) * ty) * w;
    }
    const i = (y * N + x) * 4, shade = 0.82 + 0.3 * v;
    img.data[i] = Math.min(255, R * shade); img.data[i + 1] = Math.min(255, Gc * shade); img.data[i + 2] = Math.min(255, B * shade);
    img.data[i + 3] = Math.round(255 * (0.45 + 0.55 * v));
  }
  g.putImageData(img, 0, 0);
  smokeTex[kind] = cv;
  return cv;
}
function drawSmokeLayer(g, G, list, size, cells) {
  const t = g.getTransform(), s = Math.max(0.25, Math.hypot(t.a, t.b) || 1);
  for (const kind of ['smoke', 'thermal']) {
    const mine = list.filter(x => x.kind === kind);
    if (!mine.length) continue;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    const pts = mine.map(x => G.cellCenter(x.c, x.r));
    for (const p of pts) { x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y); x1 = Math.max(x1, p.x); y1 = Math.max(y1, p.y); }
    x0 -= size; y0 -= size; x1 += size; y1 += size;
    const W = Math.max(1, Math.ceil((x1 - x0) * s)), H = Math.max(1, Math.ceil((y1 - y0) * s));
    const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
    const m = cv.getContext('2d');
    m.setTransform(s, 0, 0, s, -x0 * s, -y0 * s);
    for (const p of pts) {
      const rad = size * 0.95, gr = m.createRadialGradient(p.x, p.y, size * 0.12, p.x, p.y, rad);
      gr.addColorStop(0, 'rgba(0,0,0,.85)'); gr.addColorStop(0.55, 'rgba(0,0,0,.6)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
      m.fillStyle = gr; m.beginPath(); m.arc(p.x, p.y, rad, 0, Math.PI * 2); m.fill();
    }
    // walls hold smoke in: keep the cloud on the floor cells it covers
    if (cells) {
      m.globalCompositeOperation = 'destination-in'; m.fillStyle = '#000'; m.beginPath();
      const c0 = Math.floor(x0 / size) - 2, c1 = Math.ceil(x1 / size) + 2, r0 = Math.floor(y0 / size) - 2, r1 = Math.ceil(y1 / size) + 2;
      for (let c = c0; c <= c1; c++) for (let r = r0; r <= r1; r++) {
        const cell = cells[key(c, r)]; if (!cell || !cell.fill) continue;
        const pts2 = G.cellCorners(c, r); m.moveTo(pts2[0].x, pts2[0].y); for (let i = 1; i < pts2.length; i++) m.lineTo(pts2[i].x, pts2[i].y); m.closePath();
      }
      m.fill();
    }
    // texture the mask: drifting noise in the smoke's tone
    m.setTransform(1, 0, 0, 1, 0, 0);
    m.globalCompositeOperation = 'source-in';
    const pat = m.createPattern(smokeTexture(kind), 'repeat');
    if (pat && pat.setTransform && typeof DOMMatrix !== 'undefined') pat.setTransform(new DOMMatrix().scale(Math.max(0.5, size * s / 64)));
    m.fillStyle = pat || `rgb(${SMOKE_TONES[kind].join(',')})`; m.fillRect(0, 0, W, H);
    g.save(); g.globalAlpha = 0.78; g.drawImage(cv, x0, y0, x1 - x0, y1 - y0); g.restore();
  }
}
function cellLabel(ctx, G, c, r, text, zoom, color, dy) {
  const p = G.cellCenter(c, r);
  ctx.fillStyle = 'rgba(0,0,0,.6)'; ctx.fillText(text, p.x + 1 / zoom, p.y + (dy || 0) + 1 / zoom);
  ctx.fillStyle = color || '#ffe2a8'; ctx.fillText(text, p.x, p.y + (dy || 0));
}
function shadeCells(ctx, G, keys, style) {
  ctx.fillStyle = style;
  for (const k of keys) { const [c, r] = k.split(',').map(Number); tracePoly(ctx, G.cellCorners(c, r), false); ctx.fill(); }
}

function drawSight(ctx, map, field, zoom) {
  const G = geom(map), col = map.settings.colors;
  ctx.save();
  ctx.fillStyle = 'rgba(0,0,0,.58)';
  for (const k of field.hidden) { const [c, r] = k.split(',').map(Number); tracePoly(ctx, G.cellCorners(c, r), false); ctx.fill(); }
  ctx.fillStyle = 'rgba(0,0,0,.42)';        // beyond the range we check: not known to be in sight
  for (const k of field.far || []) { const [c, r] = k.split(',').map(Number); tracePoly(ctx, G.cellCorners(c, r), false); ctx.fill(); }
  const tint = ['', 'rgba(255,214,90,.16)', 'rgba(255,176,46,.28)', 'rgba(255,120,40,.40)', 'rgba(255,60,60,.52)'];
  for (const [k, cv] of field.seen) {
    if (!cv) continue;
    const [c, r] = k.split(',').map(Number); tracePoly(ctx, G.cellCorners(c, r), false);
    ctx.fillStyle = tint[cv]; ctx.fill();
  }
  drawSightLabels(ctx, G, field, zoom);
  // the viewer
  const p = G.cellCenter(field.from.c, field.from.r);
  ctx.strokeStyle = col.highlight; ctx.lineWidth = 2 / zoom; ctx.setLineDash([4 / zoom, 3 / zoom]);
  ctx.beginPath(); ctx.arc(p.x, p.y, G.cs * 0.62, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
  ctx.restore();
}

/* cover numerals, and smoke (−3 per Blinded level) on the cells in sight */
function drawSightLabels(ctx, G, field, zoom) {
  if (G.cs * zoom < 20) return;
  ctx.font = `700 ${Math.round(G.cs * 0.34)}px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  for (const [k, cv] of field.seen) {
    const [c, r] = k.split(',').map(Number), bl = field.blind && field.blind.get(k);
    if (cv) cellLabel(ctx, G, c, r, COVER_NAMES[cv], zoom, '#ffe2a8', bl ? -G.cs * 0.14 : 0);
    if (bl) cellLabel(ctx, G, c, r, `−${3 * bl}`, zoom, '#d6e2e4', cv ? G.cs * 0.2 : 0);
  }
}

// ---------------------------------------------------------------- range bands
const RANGE_BANDS = [['Close', 3], ['Near', 50], ['Medium', 250], ['Far', 500], ['Extreme', Infinity]];
const BAND_TINT = ['rgba(185,140,255,.24)', 'rgba(109,255,156,.18)', 'rgba(255,214,90,.20)', 'rgba(255,150,60,.22)', 'rgba(255,70,90,.24)'];
function bandOf(meters) { for (let i = 0; i < RANGE_BANDS.length; i++) if (meters <= RANGE_BANDS[i][1] + 1e-6) return i; return 4; }
/* a weapon's range bands over the cells in sight: weapon = { ar: [5 values or null] }, extras: +2 AR from
   Medium on with vision magnification */
function drawRange(ctx, map, field, world, ar, zoom, magnify) {
  const G = geom(map);
  ctx.save();
  shadeCells(ctx, G, field.hidden, 'rgba(0,0,0,.58)');
  shadeCells(ctx, G, field.far || [], 'rgba(0,0,0,.42)');
  const a = [field.from.c, field.from.r];
  ctx.font = `600 ${Math.round(G.cs * 0.26)}px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  for (const [k] of field.seen) {
    const [c, r] = k.split(',').map(Number);
    if (c === a[0] && r === a[1]) continue;
    const b = bandOf(world.distM(a, [c, r]));
    tracePoly(ctx, G.cellCorners(c, r), false);
    if (ar[b] == null) { ctx.fillStyle = 'rgba(0,0,0,.5)'; ctx.fill(); continue; }
    ctx.fillStyle = BAND_TINT[b]; ctx.fill();
  }
  // where one band gives way to the next: a line along the cell edges
  ctx.strokeStyle = 'rgba(232,246,244,.55)'; ctx.lineWidth = 1.5 / zoom;
  for (const [k] of field.seen) {
    const [c, r] = k.split(',').map(Number), b = bandOf(world.distM(a, [c, r]));
    for (let e = 0; e < G.edgeCount; e++) {
      const n = G.neighbor(c, r, e), nk = key(n.c, n.r);
      if (!field.seen.has(nk) || bandOf(world.distM(a, [n.c, n.r])) <= b) continue;
      const [p1, p2] = G.edgePoints(c, r, e); ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
    }
  }
  drawSightLabels(ctx, G, field, zoom);
  ctx.restore();
}

// ---------------------------------------------------------------- movement reach
/* steps (cells) from a cell to every room cell a token can walk to: doors closed block, like moving */
function reachSteps(map, from, maxSteps) {
  const G = geom(map), cells = map.data.cells, dist = new Map([[key(from.c, from.r), 0]]);
  let frontier = [from];
  for (let d = 1; d <= maxSteps && frontier.length; d++) {
    const next = [];
    for (const cur of frontier) for (let e = 0; e < G.edgeCount; e++) {
      const n = G.neighbor(cur.c, cur.r, e), k = key(n.c, n.r);
      if (dist.has(k) || !passable(G, cells, cur, n)) continue;
      dist.set(k, d); next.push(n);
    }
    frontier = next;
  }
  return dist;
}
/* mv = { walk, sprint, sprintMax, cellM } meters left: walk zone (cyan), sure sprint (amber), possible sprint (hatched) */
function drawReach(ctx, map, from, mv, zoom) {
  const G = geom(map), cm = mv.cellM || 2;
  const w = Math.floor((mv.walk || 0) / cm + 1e-6), s = Math.floor((mv.sprint || 0) / cm + 1e-6), sx = Math.floor((mv.sprintMax || 0) / cm + 1e-6);
  const steps = reachSteps(map, from, Math.max(w, s, sx));
  ctx.save();
  for (const [k, d] of steps) {
    if (d === 0) continue;
    const [c, r] = k.split(',').map(Number), poly = G.cellCorners(c, r);
    if (d <= w) { tracePoly(ctx, poly, false); ctx.fillStyle = 'rgba(255,255,255,.16)'; ctx.fill(); }
    else if (d <= s) { tracePoly(ctx, poly, false); ctx.fillStyle = 'rgba(255,176,46,.22)'; ctx.fill(); }
    else if (d <= sx) {
      ctx.save(); tracePoly(ctx, poly, false); ctx.clip();
      ctx.strokeStyle = 'rgba(255,176,46,.45)'; ctx.lineWidth = 1.5 / zoom;
      const p = G.cellCenter(c, r), sz = G.cs;
      for (let q = -sz; q <= sz; q += sz / 4) { ctx.beginPath(); ctx.moveTo(p.x - sz + q, p.y - sz); ctx.lineTo(p.x + sz + q, p.y + sz); ctx.stroke(); }
      ctx.restore();
    }
  }
  // outline the edge of the walking zone
  ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.lineWidth = 2.5 / zoom; ctx.setLineDash([5 / zoom, 3 / zoom]);
  for (const [k, d] of steps) {
    if (d > w) continue;
    const [c, r] = k.split(',').map(Number);
    for (let e = 0; e < G.edgeCount; e++) {
      const n = G.neighbor(c, r, e), nd = steps.get(key(n.c, n.r));
      if (nd !== undefined && nd <= w) continue;
      const [p1, p2] = G.edgePoints(c, r, e); ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
    }
  }
  ctx.setLineDash([]);
  ctx.restore();
  return steps;
}

// ---------------------------------------------------------------- area templates
const RING_TINT = ['rgba(255,60,60,.42)', 'rgba(255,140,50,.32)', 'rgba(255,214,90,.22)'];
/* blast rings (p. 114): Ground Zero within 1 m, Close 1-3 m, Near out to the blast radius */
function ringOf(d) { return d <= 1 + 1e-6 ? 0 : d <= 3 + 1e-6 ? 1 : 2; }
function templateCells(world, t) { return SightCore.areaCells(world, t.c, t.r, t.radius); }
function drawTemplates(ctx, map, world, templates, zoom, opts) {
  opts = opts || {};
  const G = geom(map), cm = world.cellM, pxPerM = (G.hex ? G.cs * SQRT3 / 2 : G.cs) / cm;
  for (const t of templates || []) {
    const cells = templateCells(world, t);
    ctx.save();
    for (const x of cells) {
      tracePoly(ctx, G.cellCorners(x.c, x.r), false);
      ctx.fillStyle = t.kind === 'blast' ? RING_TINT[ringOf(x.d)] : t.kind === 'smoke' ? 'rgba(190,200,204,.25)' : 'rgba(185,140,255,.22)';
      ctx.fill();
    }
    const p = G.cellCenter(t.c, t.r);
    ctx.strokeStyle = t.color || '#ffb02e'; ctx.lineWidth = 2 / zoom; ctx.setLineDash([6 / zoom, 4 / zoom]);
    ctx.beginPath(); ctx.arc(p.x, p.y, t.radius * pxPerM, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
    if (t.kind === 'blast') for (const rr of [1, 3]) if (rr < t.radius) { ctx.beginPath(); ctx.arc(p.x, p.y, rr * pxPerM, 0, Math.PI * 2); ctx.stroke(); }
    ctx.font = `700 ${Math.max(10, Math.round(13 / zoom))}px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
    const label = `${t.name} · ${t.radius} m`;
    ctx.fillStyle = 'rgba(0,0,0,.65)'; const tw = ctx.measureText(label).width + 8 / zoom;
    ctx.fillRect(p.x - tw / 2, p.y - t.radius * pxPerM - 18 / zoom, tw, 16 / zoom);
    ctx.fillStyle = t.color || '#ffb02e'; ctx.fillText(label, p.x, p.y - t.radius * pxPerM - 3 / zoom);
    ctx.restore();
  }
}
/* who an area catches: things = [{c, r, name}] -> [{name, ring: 'Ground zero'|'Close'|'Near'|null, dv}] */
function templateTargets(world, t, things) {
  const inside = new Map(templateCells(world, t).map(x => [key(x.c, x.r), x.d]));
  const out = [];
  for (const th of things) {
    const d = inside.get(key(th.c, th.r));
    if (d === undefined) continue;
    const ring = t.kind === 'blast' ? ringOf(d) : null;
    out.push({ name: th.name, ref: th.ref, d, ring: ring == null ? null : ['Ground zero', 'Close', 'Near'][ring], dv: ring == null || !t.dv ? null : t.dv[ring] });
  }
  return out.sort((x, y) => x.d - y.d);
}

return { MARKER_TYPES, MARKER_BY_ID, key, mix, geom, tracePoly, drawMarker, drawToken, drawTokenSprite, drawLabel, drawDoor, drawCM, cmStatus, drawStatuses, STATUS_ICONS, STATUS_COLOR, drawPing, paintedBounds, renderScene, renderSprites, pickSprite, buildIsoLayers, drawIsoLayers, visibility, makeViewport, doorOnEdge, passable, findPath, FONT, lineOfSight, sightField, sightWorld, sightMap, lightSources, drawSight, COVER_NAMES, LIGHT_LEVELS,
         drawRange, bandOf, RANGE_BANDS, reachSteps, drawReach, drawTemplates, templateTargets, templateCells };
})();
