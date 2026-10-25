/* GridGen: seeded procedural maps for square and flat-top hex grids.
   generate(opts) -> { cells: {"c,r": {fill, border, doors?}}, rooms: [{id, name, cells}] } */
window.GridGen = (() => {
'use strict';
const key = (c, r) => `${c},${r}`;

// ---------------------------------------------------------------- seeded random
function hashSeed(str) { let h = 1779033703 ^ str.length; for (let i = 0; i < str.length; i++) { h = Math.imul(h ^ str.charCodeAt(i), 3432918353); h = (h << 13) | (h >>> 19); } return h >>> 0; }
function rng(seed) {
  let a = hashSeed(String(seed)) || 1;
  const next = () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  return { next, int: (lo, hi) => lo + Math.floor(next() * (hi - lo + 1)), pick: arr => arr[Math.floor(next() * arr.length)], chance: p => next() < p,
           shuffle: arr => { for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(next() * (i + 1)); [arr[i], arr[j]] = [arr[j], arr[i]]; } return arr; } };
}

// ---------------------------------------------------------------- grid helpers
function makeGrid(gridType, width, height) {
  const G = GridCore.geom({ gridType, width, height, cellSize: 2 });
  const hex = gridType === 'hex';
  const cube = (c, r) => { const x = c, z = r - (c - (c & 1)) / 2; return { x, y: -x - z, z }; };
  const fromCube = (x, z) => ({ c: x, r: z + (x - (x & 1)) / 2 });
  return {
    G, hex, width, height,
    inBounds: (c, r) => G.inBounds(c, r),
    neighbors(c, r) { const out = []; for (let e = 0; e < G.edgeCount; e++) { const n = G.neighbor(c, r, e); if (G.inBounds(n.c, n.r)) out.push({ ...n, e }); } return out; },
    edgeTo(a, b) { for (let e = 0; e < G.edgeCount; e++) { const n = G.neighbor(a.c, a.r, e); if (n.c === b.c && n.r === b.r) return e; } return -1; },
    dist: (a, b) => G.cellDistance(a, b),
    disk(center, radius) { const out = []; for (let c = center.c - radius; c <= center.c + radius; c++) for (let r = center.r - radius - 1; r <= center.r + radius + 1; r++) if (G.inBounds(c, r) && G.cellDistance(center, { c, r }) <= radius) out.push({ c, r }); return out; },
    // straight-ish line of cells from a to b
    line(a, b) {
      if (!hex) {   // L-shape handled by caller; here: Bresenham-free straight walk
        const out = [], dc = Math.sign(b.c - a.c), dr = Math.sign(b.r - a.r); let c = a.c, r = a.r; out.push({ c, r });
        while (c !== b.c) { c += dc; out.push({ c, r }); } while (r !== b.r) { r += dr; out.push({ c, r }); } return out;
      }
      const A = cube(a.c, a.r), B = cube(b.c, b.r), n = Math.max(1, G.cellDistance(a, b)), out = [];
      for (let i = 0; i <= n; i++) {
        const t = i / n, x = A.x + (B.x - A.x) * t, y = A.y + (B.y - A.y) * t + 1e-6, z = A.z + (B.z - A.z) * t;
        let rx = Math.round(x), ry = Math.round(y), rz = Math.round(z);
        const dx = Math.abs(rx - x), dy = Math.abs(ry - y), dz = Math.abs(rz - z);
        if (dx > dy && dx > dz) rx = -ry - rz; else if (dy > dz) ry = -rx - rz; else rz = -rx - ry;
        const p = fromCube(rx, rz); if (!out.length || out[out.length - 1].c !== p.c || out[out.length - 1].r !== p.r) out.push(p);
      }
      return out;
    },
    // lattice for mazes: nodes two steps apart in every direction
    isNode(c, r) { if (!hex) return c % 2 === 1 && r % 2 === 1; const q = cube(c, r); return ((q.x % 2) + 2) % 2 === 0 && ((q.z % 2) + 2) % 2 === 0; },
    nodeStep(c, r, e) { const m = G.neighbor(c, r, e), n = G.neighbor(m.c, m.r, e); return { mid: m, node: n }; },
  };
}

// ---------------------------------------------------------------- shared pieces
function newFloor() { return { floor: new Map(), rooms: [] }; }      // floor: key -> {c,r,room:index|-1}
function carve(F, c, r, room = -1) { const k = key(c, r); const ex = F.floor.get(k); if (ex && ex.room >= 0) return; F.floor.set(k, { c, r, room }); }
function isFloor(F, c, r) { return F.floor.has(key(c, r)); }
function roomAt(F, c, r) { const f = F.floor.get(key(c, r)); return f ? f.room : -1; }

/* corridor length between two cells: the cells a corridor carved from a to b runs through, ends excluded
   (square corridors are L-shaped, so it's the Manhattan distance; hex ones run straight) */
function corridorLen(g, a, b) {
  const d = g.hex ? g.dist(a, b) : Math.abs(a.c - b.c) + Math.abs(a.r - b.r);
  return Math.max(0, d - 1);
}
/* the two closest cells of two rooms and the corridor length between them */
function closestPair(g, A, B) {
  let best = null;
  const edgeA = A.cells.filter(p => g.neighbors(p.c, p.r).length < g.G.edgeCount || g.neighbors(p.c, p.r).some(n => !A.set.has(key(n.c, n.r))));
  const edgeB = B.cells.filter(p => g.neighbors(p.c, p.r).length < g.G.edgeCount || g.neighbors(p.c, p.r).some(n => !B.set.has(key(n.c, n.r))));
  for (const a of edgeA) for (const b of edgeB) { const d = corridorLen(g, a, b); if (!best || d < best.d) best = { a, b, d }; }
  return best;
}
function placeRooms(g, R, opts, F) {
  const tries = opts.roomCount * (opts.algo === 'rooms' ? 120 : 40), gap = Math.max(1, opts.wallGap);
  const rooms = [];
  for (let t = 0; t < tries && rooms.length < opts.roomCount; t++) {
    let cells, center, bbox;
    if (!g.hex) {
      let w = R.int(opts.roomMin, opts.roomMax), h = R.int(opts.roomMin, opts.roomMax);
      let c0, r0;
      if (opts.algo === 'mazes') {   // odd sizes at odd positions line up with the maze lattice
        w |= 1; h |= 1;
        if (w + 2 > g.width || h + 2 > g.height) continue;
        c0 = R.int(0, Math.floor((g.width - w - 2) / 2)) * 2 + 1; r0 = R.int(0, Math.floor((g.height - h - 2) / 2)) * 2 + 1;
      } else {
        if (w + 2 > g.width || h + 2 > g.height) continue;
        c0 = R.int(1, g.width - w - 1); r0 = R.int(1, g.height - h - 1);
      }
      bbox = { c0, r0, c1: c0 + w - 1, r1: r0 + h - 1 };
      if (rooms.some(o => !(bbox.c1 + gap < o.bbox.c0 || o.bbox.c1 + gap < bbox.c0 || bbox.r1 + gap < o.bbox.r0 || o.bbox.r1 + gap < bbox.r0))) continue;
      cells = []; for (let c = c0; c <= bbox.c1; c++) for (let r = r0; r <= bbox.r1; r++) cells.push({ c, r });
      center = { c: Math.floor((c0 + bbox.c1) / 2), r: Math.floor((r0 + bbox.r1) / 2) };
    } else {
      const rad = R.int(Math.max(0, Math.floor((opts.roomMin - 1) / 2)), Math.max(0, Math.floor((opts.roomMax - 1) / 2)));
      center = { c: R.int(rad + 1, g.width - rad - 2), r: R.int(rad + 1, g.height - rad - 2) };
      if (center.c < 1 || center.r < 1) continue;
      if (rooms.some(o => g.dist(center, o.center) <= rad + o.rad + gap)) continue;
      cells = g.disk(center, rad); bbox = { rad };
      // organic touch: shave a few edge cells on bigger blobs
      if (rad >= 2) cells = cells.filter(p => g.dist(center, p) < rad || R.chance(0.7));
      bbox.rad = rad;
    }
    const room = { cells, center, bbox, rad: bbox.rad ?? 0, set: new Set(cells.map(p => key(p.c, p.r))) };
    // rooms & corridors: every room after the first lies within one corridor's reach of another
    if (opts.algo === 'rooms' && rooms.length && !rooms.some(o => closestPair(g, o, room).d <= opts.corridorMax)) continue;
    const idx = rooms.length;
    rooms.push(room);
    for (const p of cells) F.floor.set(key(p.c, p.r), { c: p.c, r: p.r, room: idx });
  }
  F.rooms = rooms;
  return rooms;
}

function mst(rooms, R, loops, g, opts) {
  const n = rooms.length;
  if (n < 2) return [];
  // pair distances are corridor lengths between the rooms' closest cells; the tree is the one with the
  // shortest corridors, so no corridor in it is longer than it must be (and none past the limit, given how
  // rooms were placed)
  const pair = new Map(), P = (i, j) => { const k = i < j ? i + ',' + j : j + ',' + i; let v = pair.get(k); if (!v) { v = i < j ? closestPair(g, rooms[i], rooms[j]) : (() => { const x = closestPair(g, rooms[j], rooms[i]); return { a: x.b, b: x.a, d: x.d }; })(); pair.set(k, v); } return v; };
  const inTree = new Set([0]), out = [];
  while (inTree.size < n) {
    let best = null;
    for (const i of inTree) for (let j = 0; j < n; j++) if (!inTree.has(j)) { const dd = P(i, j).d; if (!best || dd < best.d) best = { i, j, d: dd }; }
    inTree.add(best.j); out.push([best.i, best.j]);
  }
  const extra = [];
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
    if (out.some(([a, b]) => (a === i && b === j) || (a === j && b === i))) continue;
    const dd = P(i, j).d;
    if (dd > opts.corridorMax) continue;
    extra.push([i, j, dd]);
  }
  extra.sort((a, b) => a[2] - b[2]);
  for (const e of extra.slice(0, Math.round(extra.length * loops / 100))) out.push([e[0], e[1]]);
  return out.map(([i, j]) => ({ i, j, a: P(i, j).a, b: P(i, j).b }));
}

function boundaryCellToward(g, F, room, target) {
  // room cell closest to target, preferring boundary cells
  let best = null, bestD = Infinity;
  for (const p of room.cells) {
    const d = g.dist(p, target) + (g.neighbors(p.c, p.r).every(n => isFloor(F, n.c, n.r)) ? 0.5 : 0);
    if (d < bestD) { bestD = d; best = p; }
  }
  return best;
}

function carveCorridor(g, F, R, a, b, width) {
  let path;
  if (!g.hex) {
    // L-shape with random bend order
    const mid = R.chance(0.5) ? { c: b.c, r: a.r } : { c: a.c, r: b.r };
    path = g.line(a, mid).concat(g.line(mid, b).slice(1));
  } else path = g.line(a, b);
  const rad = Math.round((width - 1) / 2);
  for (const p of path) {
    const cells = rad > 0 ? g.disk(p, rad) : [p];
    if (!g.hex && width === 2) cells.push({ c: p.c + 1, r: p.r });   // 2-wide square corridor: offset band
    for (const q of cells) if (g.inBounds(q.c, q.r) && q.c > 0 && q.r > 0 && q.c < g.width - 1 && q.r < g.height - 1) carve(F, q.c, q.r);
  }
  return path;
}

// Doors where a corridor meets a room, on the room cell's edge, facing the corridor (post-process, robust to any corridor shape).
function addDoors(g, F, R, opts, out) {
  if (!opts.doors) return;
  const placed = new Set();
  for (const f of F.floor.values()) {
    if (f.room < 0) continue;
    for (const n of g.neighbors(f.c, f.r)) {
      if (!isFloor(F, n.c, n.r) || roomAt(F, n.c, n.r) >= 0) continue;     // must be a corridor cell
      // corridor must continue away from the wall (perpendicular mouth, not a corridor running alongside)
      const beyond = g.G.neighbor(n.c, n.r, n.e);
      const opp = g.G.neighbor(n.c, n.r, g.hex ? (n.e + 3) % 6 : (n.e + 2) % 4);
      const continues = g.inBounds(beyond.c, beyond.r) && isFloor(F, beyond.c, beyond.r);
      if (!continues || (opp.c !== f.c || opp.r !== f.r)) continue;
      const sig = `${f.c},${f.r}:${n.e}`;
      if (placed.has(sig) || !R.chance(opts.doorChance / 100)) { placed.add(sig); continue; }
      placed.add(sig);
      const cell = out.cells[key(f.c, f.r)];
      cell.doors = cell.doors || {}; cell.doors[n.e] = { color: opts.doorColor, open: false };
    }
  }
}

// ---------------------------------------------------------------- engine: rooms & corridors
function genRooms(g, R, opts) {
  const F = newFloor();
  const rooms = placeRooms(g, R, opts, F);
  for (const e of mst(rooms, R, opts.loops, g, opts)) carveCorridor(g, F, R, e.a, e.b, opts.corridorWidth);
  return F;
}

// ---------------------------------------------------------------- engine: rooms & mazes (Nystrom style)
function genMazes(g, R, opts) {
  const F = newFloor();
  const rooms = placeRooms(g, R, opts, F);
  // grow mazes on every free lattice node
  const regionOf = new Map();   // key -> region id (rooms 0..n-1, mazes n..)
  for (const f of F.floor.values()) regionOf.set(key(f.c, f.r), f.room);
  let region = rooms.length;
  const freeNode = (c, r) => g.inBounds(c, r) && c > 0 && r > 0 && c < g.width - 1 && r < g.height - 1 && g.isNode(c, r) && !isFloor(F, c, r) &&
    g.neighbors(c, r).every(n => roomAt(F, n.c, n.r) < 0);
  for (let c = 1; c < g.width - 1; c++) for (let r = 1; r < g.height - 1; r++) {
    if (!freeNode(c, r)) continue;
    const stack = [{ c, r }]; carve(F, c, r); regionOf.set(key(c, r), region);
    while (stack.length) {
      const cur = stack[stack.length - 1];
      const options = [];
      for (let e = 0; e < g.G.edgeCount; e++) { const { mid, node } = g.nodeStep(cur.c, cur.r, e); if (freeNode(node.c, node.r) && !isFloor(F, mid.c, mid.r)) options.push({ mid, node, e }); }
      if (!options.length) { stack.pop(); continue; }
      // windiness: prefer continuing straight
      const straight = options.find(o => o.e === cur.e);
      const pick = straight && R.chance(1 - opts.windiness / 100) ? straight : R.pick(options);
      carve(F, pick.mid.c, pick.mid.r); carve(F, pick.node.c, pick.node.r);
      regionOf.set(key(pick.mid.c, pick.mid.r), region); regionOf.set(key(pick.node.c, pick.node.r), region);
      stack.push({ ...pick.node, e: pick.e });
    }
    region++;
  }
  // connectors: wall cells touching two different regions
  const connectors = new Map();   // key -> {c,r,regions:Set}
  for (let c = 1; c < g.width - 1; c++) for (let r = 1; r < g.height - 1; r++) {
    if (isFloor(F, c, r)) continue;
    const regs = new Set(); for (const n of g.neighbors(c, r)) { const rg = regionOf.get(key(n.c, n.r)); if (rg !== undefined) regs.add(rg); }
    if (regs.size >= 2) connectors.set(key(c, r), { c, r, regions: regs });
  }
  const merged = new Map(); for (let i = 0; i < region; i++) merged.set(i, i);
  const find = i => { while (merged.get(i) !== i) i = merged.get(i); return i; };
  const doorCells = [];
  let list = R.shuffle([...connectors.values()]);
  let open = new Set(Array.from({ length: region }, (_, i) => i));
  while (open.size > 1 && list.length) {
    const con = list.shift();
    const regs = [...con.regions].map(find);
    if (new Set(regs).size < 2) { if (R.chance(opts.loops / 100 * 0.05)) { carve(F, con.c, con.r); doorCells.push(con); } continue; }
    carve(F, con.c, con.r); doorCells.push(con);
    const dest = regs[0]; for (const s of regs.slice(1)) merged.set(s, dest);
    open = new Set([...open].map(find));
  }
  // fallback: any region still isolated gets the shortest tunnel through walls to another one
  for (let guard = 0; guard < 200; guard++) {
    const comps = components(g, F);
    if (comps.length <= 1) break;
    comps.sort((a, b) => b.length - a.length);
    const target = comps[1], inTarget = new Set(target.map(p => key(p.c, p.r)));
    const prev = new Map(), queue = [];
    for (const p of target) { prev.set(key(p.c, p.r), null); queue.push(p); }
    let hit = null;
    while (queue.length && !hit) {
      const cur = queue.shift();
      for (const n of g.neighbors(cur.c, cur.r)) {
        const k = key(n.c, n.r);
        if (prev.has(k)) continue;
        if (n.c === 0 || n.r === 0 || n.c === g.width - 1 || n.r === g.height - 1) continue;
        if (isFloor(F, n.c, n.r) && !inTarget.has(k)) { hit = { ...n, from: cur }; break; }
        if (!isFloor(F, n.c, n.r)) { prev.set(k, cur); queue.push(n); }
      }
    }
    if (!hit) break;
    let cur = hit.from;
    while (cur && !inTarget.has(key(cur.c, cur.r))) { carve(F, cur.c, cur.r); doorCells.push(cur); cur = prev.get(key(cur.c, cur.r)); }
  }
  // dead-end removal
  let passes = Math.round(opts.deadEnds / 100 * 40);
  while (passes-- > 0) {
    let removed = 0;
    for (const f of [...F.floor.values()]) {
      if (f.room >= 0) continue;
      const exits = g.neighbors(f.c, f.r).filter(n => isFloor(F, n.c, n.r)).length;
      if (exits <= 1) { F.floor.delete(key(f.c, f.r)); removed++; }
    }
    if (!removed) break;
  }
  F.connectorDoors = doorCells.filter(d => isFloor(F, d.c, d.r));
  return F;
}

// ---------------------------------------------------------------- engine: caves
function genCaves(g, R, opts) {
  const F = newFloor();
  let wall = new Set();
  for (let c = 0; c < g.width; c++) for (let r = 0; r < g.height; r++) {
    const edge = c === 0 || r === 0 || c === g.width - 1 || r === g.height - 1;
    if (edge || R.chance(opts.caveFill / 100)) wall.add(key(c, r));
  }
  const around = (c, r) => {
    if (g.hex) return g.neighbors(c, r).map(n => key(n.c, n.r));
    const out = []; for (let dc = -1; dc <= 1; dc++) for (let dr = -1; dr <= 1; dr++) if (dc || dr) out.push(key(c + dc, r + dr)); return out;
  };
  const total = g.hex ? 6 : 8, thr = g.hex ? 4 : 5;
  for (let pass = 0; pass < opts.caveSmooth; pass++) {
    const next = new Set();
    for (let c = 0; c < g.width; c++) for (let r = 0; r < g.height; r++) {
      const edge = c === 0 || r === 0 || c === g.width - 1 || r === g.height - 1;
      const ks = around(c, r); const walls = ks.filter(k => { const [x, y] = k.split(',').map(Number); return !g.inBounds(x, y) || wall.has(k); }).length;
      if (edge || walls >= thr || (walls === thr - 1 && wall.has(key(c, r)) && total === 8)) next.add(key(c, r));
    }
    wall = next;
  }
  for (let c = 0; c < g.width; c++) for (let r = 0; r < g.height; r++) if (!wall.has(key(c, r))) carve(F, c, r);
  // keep the largest component, connect the others to it with tunnels
  const comps = components(g, F);
  comps.sort((a, b) => b.length - a.length);
  if (comps.length) {
    const main = comps[0];
    for (const comp of comps.slice(1)) {
      if (comp.length < opts.caveMinBlob) { for (const p of comp) F.floor.delete(key(p.c, p.r)); continue; }
      let best = null, bd = Infinity;
      for (let i = 0; i < 40; i++) { const a = R.pick(comp), b = R.pick(main), d = g.dist(a, b); if (d < bd) { bd = d; best = [a, b]; } }
      if (best) carveCorridor(g, F, R, best[0], best[1], 1);
    }
  }
  return F;
}
function components(g, F) {
  const seen = new Set(), out = [];
  for (const f of F.floor.values()) {
    const k0 = key(f.c, f.r); if (seen.has(k0)) continue;
    const comp = [], stack = [f]; seen.add(k0);
    while (stack.length) { const cur = stack.pop(); comp.push(cur); for (const n of g.neighbors(cur.c, cur.r)) { const k = key(n.c, n.r); if (!seen.has(k) && F.floor.has(k)) { seen.add(k); stack.push(F.floor.get(k)); } } }
    out.push(comp);
  }
  return out;
}

// ---------------------------------------------------------------- entry
const DEFAULTS = {
  gridType: 'square', width: 48, height: 32, algo: 'rooms', seed: '',
  roomCount: 9, roomMin: 3, roomMax: 8, wallGap: 1, corridorWidth: 1, corridorMax: 20,
  loops: 15, windiness: 50, deadEnds: 80,
  caveFill: 45, caveSmooth: 4, caveMinBlob: 12,
  doors: true, doorChance: 60, groupRooms: true,
  fill: '#1c4a52', border: '#4fd8dc', doorColor: '#2de2e6',
};
function generate(userOpts) {
  const opts = { ...DEFAULTS, ...userOpts };
  opts.roomMin = Math.max(1, Math.min(opts.roomMin, opts.roomMax));
  opts.corridorMax = Math.max(Math.max(1, opts.wallGap), +opts.corridorMax || DEFAULTS.corridorMax);   // rooms keep at least the wall gap apart
  const seed = opts.seed === '' || opts.seed == null ? String(Math.floor(Math.random() * 1e9)) : String(opts.seed);
  const R = rng(seed), g = makeGrid(opts.gridType, opts.width, opts.height);
  const F = opts.algo === 'caves' ? genCaves(g, R, opts) : opts.algo === 'mazes' ? genMazes(g, R, opts) : genRooms(g, R, opts);
  const out = { cells: {}, rooms: [], seed };
  for (const f of F.floor.values()) out.cells[key(f.c, f.r)] = { fill: opts.fill, border: opts.border };
  if (opts.algo === 'mazes') {
    if (opts.doors) for (const d of F.connectorDoors || []) {
      // door on the room cell edge that faces the connector; skip connectors that join two mazes
      for (const n of g.neighbors(d.c, d.r)) {
        if (roomAt(F, n.c, n.r) < 0 || !R.chance(opts.doorChance / 100)) continue;
        const e = g.edgeTo(n, d); const cell = out.cells[key(n.c, n.r)]; cell.doors = cell.doors || {}; cell.doors[e] = { color: opts.doorColor, open: false };
        break;
      }
    }
  } else addDoors(g, F, R, opts, out);
  if (opts.groupRooms) F.rooms.forEach((rm, i) => {
    const cells = rm.cells.map(p => key(p.c, p.r)).filter(k => out.cells[k]);
    if (cells.length) out.rooms.push({ id: Math.random().toString(36).slice(2, 10), name: `Room ${i + 1}`, cells });
  });
  return out;
}
return { generate, DEFAULTS, _test: { makeGrid, rng, placeRooms, mst, newFloor } };
})();
