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
      tracePoly(g, corners, snap); g.fillStyle = fill; g.fill();
      if (cell.borderOn !== false && opts.borders !== false) {
        const b = cell.border || col.cellBorder;
        g.strokeStyle = vis === 'dim' ? mix(b, col.revealedTint, 0.5) : b;
        g.lineWidth = Math.max(1, pixel ? Math.round(size / 16) : size / 16); g.stroke();
      }
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

return { MARKER_TYPES, MARKER_BY_ID, key, mix, geom, tracePoly, drawMarker, drawToken, drawTokenSprite, drawLabel, drawDoor, drawCM, cmStatus, drawStatuses, STATUS_ICONS, STATUS_COLOR, drawPing, paintedBounds, renderScene, renderSprites, buildIsoLayers, drawIsoLayers, visibility, makeViewport, doorOnEdge, passable, findPath, FONT };
})();
