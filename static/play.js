/* Player app: map (GridMap player view), character sheet, store, runs and wiki in one page. */
(() => {
'use strict';
const $ = id => document.getElementById(id);
const S = {
  st: null, view: 'map', sheet: null, sheetRev: null, runsSig: '', storeCat: 'All',
  // map
  map: null, explored: new Set(), hover: null, drag: null, spaceDown: false, busy: false, legend: true,
  fitted: false, lastMapId: null, sceneDirty: true, sceneZoom: 1, frame: null, pathCache: null, ghost: null, pingFrame: null, lastTap: 0, clockSkew: 0, iso: {}, sceneIso: null,
};
let CAT = null, sheetUI = null, mapRoller = null;
const post = (path, body) => api('/api/me/' + path, 'POST', body || {});

// ================================================================ tabs
function setView(v) {
  if (!['map', 'sheet', 'store', 'runs', 'wiki'].includes(v)) v = 'map';
  S.view = v;
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  document.querySelectorAll('.view').forEach(s => s.classList.toggle('active', s.id === 'view-' + v));
  if (location.hash !== '#' + v) history.replaceState(null, '', '#' + v);
  if (v === 'map') { requestDraw(); }
  if (v === 'sheet' && sheetUI) sheetUI.render();
  if (v === 'store') renderStore();
  if (v === 'runs') loadRuns();
}
document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => setView(b.dataset.view));
document.addEventListener('click', e => { const g = e.target.closest('[data-goto]'); if (g) setView(g.dataset.goto); });
window.addEventListener('hashchange', () => setView(location.hash.slice(1)));

// account menu
$('btn-account').onclick = e => { e.stopPropagation(); $('account-menu').hidden = !$('account-menu').hidden; };
document.addEventListener('click', e => { if (!e.target.closest('.menu')) $('account-menu').hidden = true; });
$('btn-password').onclick = async () => {
  $('account-menu').hidden = true;
  const cur = h('input', { type: 'password', autocomplete: 'current-password', required: true });
  const nw = h('input', { type: 'password', autocomplete: 'new-password', minlength: 8, required: true });
  const ok = await UI.modal('Change password', h('div', h('label.stack', 'Current password', cur), h('label.stack', 'New password (8+ characters)', nw)), { ok: 'Change', narrow: true });
  if (!ok) return;
  try { await post('password', { current: cur.value, new: nw.value }); toast('Password changed.'); } catch (e) { toast(e.message); }
};

// ================================================================ header chips
function renderChips() {
  const me = S.st && S.st.me; if (!me) return;
  $('me-name').textContent = me.name; $('me-dot').style.background = me.color;
  $('game-name').textContent = S.st.game.name;
  $('chip-karma').textContent = me.karma;
  $('chip-nuyen').textContent = money(me.nuyen);
  $('chip-edge').textContent = `${me.edge.cur}/${me.edge.max}`;
  $('chip-edge-pips').replaceChildren(SR.pips(me.edge.cur, me.edge.max));
  const st = me.cm.status;
  $('chip-health').replaceChildren(h('span.k', 'Health'), h('b', { class: st === 'OK' ? 'good' : st === 'Wounded' ? 'warn' : 'bad' }, st === 'OK' ? 'OK' : st),
    me.cm.wound ? h('span.hint', ` ${me.cm.wound} dice`) : '');
  $('badge-sheet').hidden = me.status === 'approved';
  $('badge-sheet').textContent = me.status === 'waiting' ? '…' : '!';
  $('badge-sheet').title = me.status === 'waiting' ? 'Waiting for GM approval' : 'Finish your character and submit it';
  $('badge-runs').hidden = !S.st.activeRuns; $('badge-runs').textContent = S.st.activeRuns;
  $('store-nuyen').textContent = money(me.nuyen);
  document.title = `${me.name} · ShadowGrid`;
}

// ================================================================ state polling
async function refresh(force) {
  if (!force && (document.hidden || S.busy || S.drag)) return;
  try {
    const st = await api('/api/me/state?since=' + encodeURIComponent(force ? '' : (S.st ? S.st.version : '')));
    if (st.unchanged) return;
    applyState(st);
  } catch (e) { /* transient */ }
}
function applyState(st) {
  S.st = st;
  if (st.view.now) S.clockSkew = Date.now() / 1000 - st.view.now;
  renderChips();
  applyView(st.view);
  SR.renderLog($('p-log'), st.rolls);
  if (sheetUI) sheetUI.updateLog(st.rolls);
  if (st.sheetRev !== S.sheetRev) {
    S.sheetRev = st.sheetRev;
    if (sheetUI && !sheetUI.editing()) sheetUI.reload();
  }
  const sig = JSON.stringify(st.runsSig);
  if (sig !== S.runsSig) { S.runsSig = sig; if (S.view === 'runs') loadRuns(); }
}
function onSheet(sh) {
  S.sheet = sh;
  if (S.st) { Object.assign(S.st.me, sh.player); renderChips(); }
  renderCondition();
  if (mapRoller) mapRoller.render();
  if (S.view === 'store') renderStore();
}
function onRolled(res) {
  if (res.me && S.st) { Object.assign(S.st.me, res.me); renderChips(); }
  if (res.rolls) { SR.renderLog($('p-log'), res.rolls); if (sheetUI) sheetUI.updateLog(res.rolls); }
  if (res.me && sheetUI) { sheetUI.mergeMe(res.me); }
  if (mapRoller && S.view !== 'map') mapRoller.render();
}

// ================================================================ map sidebar
function renderCondition() {
  const el = $('p-condition'); el.innerHTML = '';
  if (!S.sheet) return;
  const dv = S.sheet.derived;
  const cm = { p: dv.physical_damage, pm: dv.physical_boxes, s: dv.stun_damage, sm: dv.stun_boxes, ov: dv.overflow_boxes };
  const set = async (track, value) => { try { sheetUI.setSheet(await api('/api/me/sheet/action', 'POST', { action: 'set_damage', track, value })); } catch (e) { toast(e.message); } };
  el.append(SR.monitor('physical', cm, { onSet: set, compact: true, showTools: false }), SR.monitor('stun', cm, { onSet: set, compact: true, showTools: false }));
  const ch = S.sheet.char;
  el.append(h('div.row.between', h('span', 'Edge ', SR.pips(ch.current_edge, dv.edge_max)),
    h('button.small', { type: 'button', disabled: !ch.current_edge, onclick: () => SR.edgeMenu(S.sheet, post, res => { onRolled(res); sheetUI.reload(); }) }, 'Spend Edge…')));
  if (dv.wound_modifier) el.append(h('p.hint.mb0', `Wound modifier ${dv.wound_modifier} dice (applied to rolls).`));
}

// ================================================================ map view (GridMap player view)
const { key, geom, tracePoly, drawMarker, renderScene, makeViewport, MARKER_BY_ID, MARKER_TYPES, doorOnEdge, findPath, drawPing } = GridCore;
const canvas = $('map'), ctx2d = canvas.getContext('2d'), wrap = $('canvas-wrap');
const scene = document.createElement('canvas'), sctx = scene.getContext('2d');
const mini = document.createElement('canvas'), mctx = mini.getContext('2d');
const vp = makeViewport(canvas, wrap, $('minimap'), () => S.map);
$('minimap').addEventListener('minimap-move', requestDraw);
function loadIso() { try { return localStorage.getItem('sg.iso') !== '0'; } catch { return true; } }
function setIso(on) { vp.setIso(on); $('iso-toggle').checked = on; try { localStorage.setItem('sg.iso', on ? '1' : '0'); } catch { /* ignore */ } if (S.map) focusToken(); invalidate(); }
vp.setIso(loadIso());
$('iso-toggle').checked = vp.iso;
$('iso-toggle').onchange = e => setIso(e.target.checked);

function applyView(v) {
  S.st.view = v; S.ghost = null; S.pathCache = null;
  $('map-empty').hidden = !!v.map;
  if (!v.map) { S.map = null; $('p-help').textContent = 'Your GM has not placed you on a map yet. This page updates on its own.'; renderActions(); invalidate(); return; }
  $('p-help').textContent = v.token ? `${v.map.name}. Drag your token or click a room you can reach. Doors on your cell open below or by clicking them.` : `${v.map.name}. Waiting for the GM to place your token.`;
  const m = v.map;
  S.map = { gridType: m.gridType, width: m.width, height: m.height, cellSize: m.cellSize,
    settings: { colors: m.settings.colors, showGrid: m.settings.showGrid }, data: { cells: m.cells, markers: m.markers, rooms: [] } };
  S.explored = new Set(Object.keys(m.cells).filter(k => m.cells[k].vis === 'full'));
  if (!S.fitted || S.lastMapId !== m.id) { if (S.view === 'map') { focusToken(); S.fitted = true; S.lastMapId = m.id; } }
  renderActions(); renderLegend(); invalidate();
}
/* fit the map, then zoom in on our own token so the explored area is readable */
function focusToken() {
  vp.fit();
  const t = S.st && S.st.view.token; if (!t || !S.map) return;
  const G = geom(S.map), c = G.cellCenter(t.c, t.r);
  vp.zoom = Math.max(vp.zoom, 46 / G.cs);
  vp.centerOn(c.x, c.y);
}
function token() { return S.ghost || (S.st && S.st.view.token); }
function viewModel() {
  const tokens = (S.st.view.others || []).map(o => ({ ...o, me: false }));
  const t = token();
  if (t) tokens.push({ c: t.c, r: t.r, color: S.st.me.color, name: S.st.me.name, me: true, cm: S.st.me.cm });
  return { mode: 'player', explored: S.explored, mapStation: !!S.st.view.map.mapStation, tokens };
}
function pathTo(cell) {
  const t = S.st.view.token; if (!t || !cell) return null;
  const k = key(cell.c, cell.r);
  if (S.pathCache && S.pathCache.k === k) return S.pathCache.path;
  const path = findPath(geom(S.map), S.map.data.cells, t, cell);
  S.pathCache = { k, path };
  return path;
}
function invalidate() { S.sceneDirty = true; requestDraw(); }
function requestDraw() { if (!S.frame) S.frame = requestAnimationFrame(() => { S.frame = null; draw(); }); }
function draw() {
  if (S.view !== 'map') return;
  const dpr = window.devicePixelRatio || 1, W = wrap.clientWidth, H = wrap.clientHeight;
  if (!W || !H) return;
  if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) { canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr); }
  ctx2d.setTransform(1, 0, 0, 1, 0, 0);
  ctx2d.fillStyle = S.map ? S.map.settings.colors.fog : '#050707'; ctx2d.fillRect(0, 0, canvas.width, canvas.height);
  if (!S.map) return;
  if (!S.fitted || S.lastMapId !== S.st.view.map.id) { focusToken(); S.fitted = true; S.lastMapId = S.st.view.map.id; S.sceneDirty = true; }
  const v = viewModel(), G = geom(S.map), { w, h: hh } = G.mapPixelSize();
  if (S.sceneDirty || Math.abs(vp.zoom - S.sceneZoom) > 0.5 || S.sceneIso !== vp.iso) {
    const q = Math.min(3, Math.max(1, Math.ceil(vp.zoom * dpr)));
    if (vp.iso) GridCore.buildIsoLayers(S.iso, S.map, v, q);
    else {
      const ow = Math.ceil(w * q), oh = Math.ceil(hh * q);
      if (scene.width !== ow || scene.height !== oh) { scene.width = ow; scene.height = oh; }
      sctx.setTransform(q, 0, 0, q, 0, 0); sctx.clearRect(0, 0, w, hh); renderScene(sctx, S.map, v, { pixel: false }); scene._q = q;
    }
    const { MW, MH, scale } = vp.minimapSize();
    if (mini.width !== MW || mini.height !== MH) { mini.width = MW; mini.height = MH; }
    mctx.setTransform(scale, 0, 0, scale, 0, 0); mctx.clearRect(0, 0, w, hh); renderScene(mctx, S.map, v, { pixel: false, grid: false, borders: false, forExport: true });
    S.sceneDirty = false; S.sceneZoom = vp.zoom; S.sceneIso = vp.iso;
  }
  if (vp.iso) GridCore.drawIsoLayers(ctx2d, S.iso, vp, dpr, G.cs);
  else { ctx2d.setTransform(...vp.matrix(dpr)); const q = scene._q || 1; ctx2d.drawImage(scene, 0, 0, scene.width / q, scene.height / q); }
  ctx2d.setTransform(...vp.matrix(dpr));
  // ---- world-space overlays (lie on the floor)
  const target = S.drag && S.drag.token ? S.hover : (S.hover && !S.busy ? S.hover : null);
  const path = target ? pathTo(target) : null;
  if (path && path.length) {
    const t = S.st.view.token;
    ctx2d.strokeStyle = 'rgba(0,229,255,.85)'; ctx2d.lineWidth = 2.5 / vp.zoom; ctx2d.setLineDash([5 / vp.zoom, 4 / vp.zoom]); ctx2d.lineJoin = 'round';
    ctx2d.beginPath(); const s0 = G.cellCenter(t.c, t.r); ctx2d.moveTo(s0.x, s0.y);
    for (const p of path) { const c = G.cellCenter(p.c, p.r); ctx2d.lineTo(c.x, c.y); }
    ctx2d.stroke(); ctx2d.setLineDash([]);
    ctx2d.strokeStyle = S.map.settings.colors.highlight; ctx2d.lineWidth = 2 / vp.zoom;
    tracePoly(ctx2d, G.cellCorners(target.c, target.r), false); ctx2d.stroke();
  } else if (S.hover && S.explored.has(key(S.hover.c, S.hover.r))) {
    ctx2d.strokeStyle = 'rgba(255,255,255,.3)'; ctx2d.lineWidth = 1.5 / vp.zoom;
    tracePoly(ctx2d, G.cellCorners(S.hover.c, S.hover.r), false); ctx2d.stroke();
  }
  const nowS = Date.now() / 1000; let activePing = false;
  for (const pg of S.st.view.pings || []) { const age = nowS - (S.clockSkew || 0) - pg.t; if (age < 0 || age > 10) continue; activePing = true; const { x, y } = G.cellCenter(pg.c, pg.r); drawPing(ctx2d, x, y, G.cs, pg.color, age); }
  if (activePing && !S.pingFrame) S.pingFrame = setTimeout(() => { S.pingFrame = null; requestDraw(); }, 60);
  // ---- screen-space: upright sprites (iso), dragged token, labels
  ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0);
  const dragging = S.drag && S.drag.token && S.drag.pt;
  if (vp.iso) GridCore.renderSprites(ctx2d, S.map, v, vp, { skipToken: t => dragging && t.me });
  if (dragging) {
    const p = vp.toScreen(S.drag.pt.x, S.drag.pt.y), tok = { color: S.st.me.color, name: S.st.me.name, me: true };
    if (vp.iso) GridCore.drawTokenSprite(ctx2d, p.x, p.y, G.cs * vp.zoom * 0.7, tok, S.map.settings.colors);
    else GridCore.drawToken(ctx2d, p.x, p.y, G.cs * vp.zoom * 0.7, tok, S.map.settings.colors, false);
  }
  const hl = hoverLabel();
  if (hl) { const c = G.cellCenter(hl.c, hl.r), p = vp.toScreen(c.x, c.y); GridCore.drawLabel(ctx2d, p.x, p.y + G.cs * vp.zoom * 0.35, hl.text, G.cs * vp.zoom); }
  vp.drawMinimap(mini);
}
function hoverLabel() {
  if (!S.hover || !S.map) return null;
  const mk = S.map.data.markers.find(x => x.c === S.hover.c && x.r === S.hover.r);
  const tk = (S.st.view.others || []).find(o => o.c === S.hover.c && o.r === S.hover.r);
  const parts = [];
  if (mk) { if (mk.label) parts.push(mk.label); if (mk.cm) { const st = GridCore.cmStatus(mk.cm); if (st !== 'OK') parts.push(st); } if (mk.isLink) parts.push('→ ' + (mk.targetName || 'somewhere')); }
  if (tk) parts.push(tk.name + (tk.cm && tk.cm.status !== 'OK' ? ` (${tk.cm.status})` : ''));
  return parts.length ? { c: S.hover.c, r: S.hover.r, text: parts.join(' · ') } : null;
}
function renderActions() {
  const el = $('p-actions'); el.innerHTML = '';
  if (!S.st || !S.st.view.map) return;
  const G = geom(S.map);
  for (const d of S.st.view.doorsHere || []) {
    const b = h('button', { type: 'button', disabled: !!d.locked, onclick: () => act('door', { edge: d.edge }) },
      h('span.dot', { style: { background: d.color } }), d.locked ? `${G.edgeNames[d.edge]} door is locked` : `${d.open ? 'Close' : 'Open'} ${G.edgeNames[d.edge].toLowerCase()} door`);
    el.append(b);
  }
  if (S.st.view.canTravel) el.append(h('button.primary', { type: 'button', onclick: () => act('travel') }, `Travel to ${S.st.view.canTravel.mapName}`));
  const others = S.st.view.others || [];
  if (others.length) el.append(h('p.hint', 'Nearby: ' + others.map(o => o.name + (o.cm && o.cm.status !== 'OK' ? ` (${o.cm.status})` : '')).join(', ')));
}
function renderLegend() {
  const el = $('legend'); el.hidden = !S.legend; el.innerHTML = '';
  if (el.hidden || !S.map) return;
  const groups = new Map(), col = S.map.settings.colors;
  for (const m of S.map.data.markers) { const k = m.type + '|' + (m.color || col.markerDefault); groups.set(k, (groups.get(k) || 0) + 1); }
  if (!groups.size) return;
  el.append(h('h4', 'Legend'));
  for (const [k, n] of groups) {
    const [type, color] = k.split('|');
    const cv = h('canvas', { width: 36, height: 36 }); drawMarker(cv.getContext('2d'), 18, 18, 26, type, color, col.markerText, false);
    el.append(h('div.legend-row', cv, h('span', (MARKER_BY_ID[type] || MARKER_TYPES[0]).name), h('span.count', '×' + n)));
  }
}
$('legend-toggle').onchange = e => { S.legend = e.target.checked; renderLegend(); };
async function ping(cell) {
  if (!cell) return;
  S.st.view.pings = (S.st.view.pings || []).concat([{ c: cell.c, r: cell.r, t: Date.now() / 1000 - (S.clockSkew || 0), color: S.st.me.color, name: S.st.me.name }]); requestDraw();
  try { await post('ping', cell); } catch (e) { toast(e.message); }
}
async function act(path, body) {
  if (S.busy) return; S.busy = true;
  try { applyView(await post(path, body)); } catch (e) { S.ghost = null; invalidate(); toast(e.message); }
  S.busy = false;
}
function moveTo(cell) {
  if (!cell || !S.st.view.token) return;
  const path = pathTo(cell);
  if (!path || !path.length) return;
  S.ghost = { c: cell.c, r: cell.r }; invalidate();
  act('move', { c: cell.c, r: cell.r });
}
canvas.addEventListener('contextmenu', e => e.preventDefault());
canvas.addEventListener('pointerdown', ev => {
  canvas.setPointerCapture(ev.pointerId);
  const { sx, sy } = vp.canvasPoint(ev), pt = vp.screenToMap(sx, sy);
  const pan = ev.button === 1 || ev.button === 2 || S.spaceDown;
  const t = S.st && S.st.view.token, cell = S.map ? geom(S.map).pointToCell(pt.x, pt.y) : null;
  const onToken = !pan && t && cell && cell.c === t.c && cell.r === t.r;
  S.drag = { sx, sy, px: vp.panX, py: vp.panY, moved: false, token: onToken, tap: !pan, pt };
  canvas.classList.toggle('panning', pan);
});
canvas.addEventListener('pointermove', ev => {
  const { sx, sy } = vp.canvasPoint(ev), pt = vp.screenToMap(sx, sy);
  S.hover = S.map ? geom(S.map).pointToCell(pt.x, pt.y) : null;
  if (S.drag) {
    if (Math.hypot(sx - S.drag.sx, sy - S.drag.sy) > 6) S.drag.moved = true;
    if (S.drag.token) S.drag.pt = pt;
    else if (S.drag.moved) { vp.panX = S.drag.px + (sx - S.drag.sx); vp.panY = S.drag.py + (sy - S.drag.sy); }
  }
  requestDraw();
});
canvas.addEventListener('pointerup', ev => {
  const d = S.drag; S.drag = null; canvas.classList.remove('panning');
  if (d && S.map) {
    const { sx, sy } = vp.canvasPoint(ev), pt = vp.screenToMap(sx, sy), cell = geom(S.map).pointToCell(pt.x, pt.y);
    const t = S.st.view.token;
    if (d.tap && !d.moved) { const nowMs = Date.now(); if (nowMs - S.lastTap < 350 && cell) { S.lastTap = 0; ping(cell); requestDraw(); return; } S.lastTap = nowMs; }
    if (d.token && d.moved) moveTo(cell);
    else if (d.tap && !d.moved && cell && t && cell.c === t.c && cell.r === t.r) {
      const G = geom(S.map), e = G.nearestEdge(t.c, t.r, pt.x, pt.y);
      if (doorOnEdge(G, S.map.data.cells, t.c, t.r, e)) act('door', { edge: e });
    } else if (d.tap && !d.moved) moveTo(cell);
  }
  requestDraw();
});
canvas.addEventListener('pointerleave', () => { S.hover = null; requestDraw(); });
canvas.addEventListener('wheel', ev => { ev.preventDefault(); const { sx, sy } = vp.canvasPoint(ev); vp.zoomAt(sx, sy, Math.exp(-ev.deltaY * 0.0015)); requestDraw(); }, { passive: false });
const ARROWS = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
window.addEventListener('keydown', ev => {
  if (S.view !== 'map' || ev.target.matches('input, textarea, select') || document.querySelector('dialog[open]')) return;
  if (ev.code === 'Space') { S.spaceDown = true; canvas.classList.add('panning'); ev.preventDefault(); }
  if (ev.key.toLowerCase() === 'f' && S.map) { vp.fit(); invalidate(); }
  if (ev.key.toLowerCase() === 'c' && S.map) { focusToken(); invalidate(); }
  if (ev.key.toLowerCase() === 'i' && !ev.ctrlKey && !ev.metaKey) setIso(!vp.iso);
  if (ARROWS[ev.key] && S.map && S.st.view.token && !S.busy) {
    ev.preventDefault();
    const t = S.st.view.token, G = geom(S.map), [dc, dr] = ARROWS[ev.key];
    let target = { c: t.c + dc, r: t.r + dr };
    if (G.hex) {
      let best = null, bestDot = 0.3;
      for (let e = 0; e < G.edgeCount; e++) { const n = G.neighbor(t.c, t.r, e), a0 = G.cellCenter(t.c, t.r), b0 = G.cellCenter(n.c, n.r), a = vp.toScreen(a0.x, a0.y), b = vp.toScreen(b0.x, b0.y); const vx = b.x - a.x, vy = b.y - a.y, len = Math.hypot(vx, vy); const dot = (vx * dc + vy * dr) / len; if (dot > bestDot) { bestDot = dot; best = n; } }
      target = best;
    }
    if (target) moveTo(target);
  }
});
window.addEventListener('keyup', ev => { if (ev.code === 'Space') { S.spaceDown = false; canvas.classList.remove('panning'); } });
new ResizeObserver(() => requestDraw()).observe(wrap);

// ================================================================ store
function renderStore() {
  if (!CAT || !S.sheet) return;
  const ch = S.sheet.char, locked = S.sheet.locked;
  $('store-nuyen').textContent = money(ch.nuyen);
  $('store-note').replaceChildren(locked ? h('div.banner', h('p', 'Your sheet is approved: purchases are final.')) :
    h('div.banner.info', h('p', 'Character creation: anything you buy can be returned for a full refund from the Gear section of your character.')));
  const cats = $('store-cats'); cats.innerHTML = '';
  for (const c of ['All', ...CAT.gearCategories]) cats.append(h('button' + (S.storeCat === c ? '.active' : ''), { type: 'button', onclick: () => { S.storeCat = c; renderStore(); } }, c));
  const q = $('store-search').value.trim().toLowerCase();
  const grid = $('store-grid'); grid.innerHTML = '';
  const owned = {}; for (const c of CAT.gearCategories) for (const it of ch.gear[c] || []) owned[it.name] = (owned[it.name] || 0) + 1;
  let n = 0;
  for (const cat of CAT.gearCategories) {
    if (S.storeCat !== 'All' && S.storeCat !== cat) continue;
    CAT.gear[cat].forEach((it, i) => {
      if (q && !JSON.stringify(it).toLowerCase().includes(q)) return;
      n++;
      const short = it.Price > ch.nuyen;
      grid.append(h('div.item-card', h('div.cat', cat + (it.Type ? ' · ' + it.Type : '')), h('h4', it.name, owned[it.name] ? h('span.tag.approved', { style: { marginLeft: '.4rem' } }, `owned ×${owned[it.name]}`) : null),
        SR.itemDetails(it, ['Type']),
        h('div.buy', h('span.price' + (short ? '.short' : ''), money(it.Price)),
          h('button.primary.small', { type: 'button', disabled: short, title: short ? `You need ${money(it.Price - ch.nuyen)} more` : '', onclick: () => buy(cat, { index: i }, it) }, short ? 'Not enough ¥' : 'Buy'))));
    });
  }
  if (!n) grid.append(h('p.empty', 'Nothing matches. Try another search, or create a custom item.'));
}
async function buy(category, payload, it) {
  if (S.sheet.locked && !await UI.confirm(`Buy ${it.name} for ${money(it.Price || 0)}? Purchases are final.`, { ok: 'Buy' })) return;
  try {
    const sh = await api('/api/me/sheet/action', 'POST', { action: 'buy', category, ...payload });
    sheetUI.setSheet(sh);
    toast(sh.message);
  } catch (e) { toast(e.message, 4000); }
}
$('store-search').oninput = () => renderStore();
$('store-custom').onclick = async () => {
  const cat = h('select', CAT.gearCategories.map(c => option(c, c, c === S.storeCat)));
  const ok = await UI.modal('Custom item', h('div', h('label.stack', 'Category', cat), h('p.hint', 'For gear that is not in the list. You pay the price you enter; your GM sees custom items marked as “custom”.')), { ok: 'Next', narrow: true });
  if (!ok) return;
  const it = await SR.editItem(cat.value, {}, { title: `Custom ${cat.value}`, ok: 'Buy' });
  if (it) buy(cat.value, { item: it }, it);
};

// ================================================================ runs
async function loadRuns() {
  try { renderRuns((await api('/api/me/runs')).runs); } catch (e) { /* transient */ }
}
function renderRuns(runs) {
  const el = $('runs-list'); el.innerHTML = '';
  if (!runs.length) { el.append(h('div.card.empty', h('h3', 'No contracts yet'), h('p', 'When your GM gives you a run it shows up here, with its tasks and the reward.'))); return; }
  for (const r of runs) {
    const tasks = h('ul.tasks');
    r.tasks.forEach(t => tasks.append(h('li' + (t.completed ? '.done' : ''), h('span.tick', t.completed ? '✓' : ''), h('span.t', t.description), t.mandatory ? h('span.mand', { title: 'Mandatory' }, '*') : null)));
    const reward = r.status === 'Completed' ? h('span', 'Paid ', h('b.good', money(r.payout)), ' to each runner') :
      r.status === 'Abandoned' ? h('span.hint', 'Abandoned') : h('span', 'Reward ', h('b', money(r.reward)), r.tasks.length ? h('span.hint', ` · currently ${money(r.scaledPayout)} (${r.progress}% of tasks)`) : '');
    el.append(h('div.run-card' + (r.status === 'Abandoned' ? '.dim' : ''),
      h('div.head', h('h3', r.name), h('span.tag.' + r.status.toLowerCase(), r.status)),
      r.description ? h('p', { style: { whiteSpace: 'pre-wrap' } }, r.description) : null,
      r.tasks.length ? h('div.bar', h('span', { style: { width: r.progress + '%' } })) : null,
      r.tasks.length ? tasks : null,
      r.tasks.some(t => t.mandatory) ? h('p.hint.mb0', '* mandatory. The GM ticks tasks as you complete them.') : null,
      h('div', reward)));
  }
}

// ================================================================ boot
async function boot() {
  try {
    CAT = await SR.catalog();
    await refresh(true);
    sheetUI = Sheet.mount($('sheet-root'), { gm: false, sheetUrl: '/api/me/sheet', actionUrl: '/api/me/sheet/action', post, onSheet,
      openStore: () => setView('store'), log: () => (S.st ? S.st.rolls : []), onRolled });
    await sheetUI.load();
    S.sheetRev = S.st.sheetRev;
    mapRoller = SR.roller({ compact: true, getSheet: () => S.sheet, post, onRolled });
    $('p-roller').append(mapRoller); mapRoller.render();
    Wiki($('wiki'), CAT.wiki);
    const first = location.hash.slice(1) || (S.st.me.status !== 'approved' && !S.st.view.map ? 'sheet' : 'map');
    setView(first);
    setInterval(() => refresh(false), 1200);
  } catch (e) { if (e.message !== 'auth') toast('Could not load: ' + e.message, 6000); }
}
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(true); });
boot();
})();
