/* ShadowGrid map editor for the gamemaster. Depends on api.js, gridcore.js and srui.js. */
(() => {
'use strict';
const { MARKER_TYPES, MARKER_BY_ID, key, geom, tracePoly, drawMarker, renderScene, makeViewport, doorOnEdge, drawPing, paintedBounds } = GridCore;
const MAP_ID = document.body.dataset.mapId;
const $ = id => document.getElementById(id);

const S = {
  map: null, ctx: null,
  mode: 'edit', tool: 'paint', viewAs: '',
  dragging: null, hover: null, hoverPt: null, selected: null,
  spaceDown: false, brush: 1, markerType: 'poi',
  dirty: false, saveTimer: null,
  sceneDirty: true, sceneZoom: 1, frame: null,
  fogQueue: null, fogTimer: null,
  version: null, pollTimer: null, pollInterval: 20000, playersSig: '', rollsSig: '', follow: false, pingFrame: null, iso: {}, sceneIso: null,
  rt: { doors: new Set(), markers: new Set(), all: false },   // runtime fields the editor itself changed since the last save
  tracker: null, templateNpc: null, fp: false, fpCam: null,
};

const canvas = $('map'), ctx2d = canvas.getContext('2d'), wrap = $('canvas-wrap');
const scene = document.createElement('canvas'), sctx = scene.getContext('2d');
const mini = document.createElement('canvas'), mctx = mini.getContext('2d');
const vp = makeViewport(canvas, wrap, $('minimap'), () => S.map);
$('minimap').addEventListener('minimap-move', requestDraw);
function isoPref(mode) { try { const v = localStorage.getItem('sg.iso.' + mode); return v === null ? mode === 'play' : v === '1'; } catch { return mode === 'play'; } }
function setIso(on, remember = true) {
  vp.setIso(on); $('iso-toggle').checked = on;
  if (remember) try { localStorage.setItem('sg.iso.' + S.mode, on ? '1' : '0'); } catch { /* ignore */ }
  invalidate();
}
$('iso-toggle').onchange = e => setIso(e.target.checked);

/* first-person view: a free GM camera that walks the rooms (and through closed doors); it never moves tokens */
function fpPref() { try { return localStorage.getItem('sg.fp.gm') === '1'; } catch { return false; } }
function fpStart() {
  const p = player(), t = p && pms(p).token;
  if (t) return { c: t.c, r: t.r };
  if (S.selected && cells()[key(S.selected.c, S.selected.r)]?.fill) return { c: S.selected.c, r: S.selected.r };
  for (const q of S.ctx.players) { const tk = (q.state.maps || {})[MAP_ID]?.token; if (tk && q.currentMapId === MAP_ID) return { c: tk.c, r: tk.r }; }
  // a room cell in the open (most painted neighbours), so the first look is not into a corner
  const g = G(); let k = null, best = -1;
  for (const kk of Object.keys(cells())) {
    if (!cells()[kk].fill) continue;
    const [c, r] = kk.split(',').map(Number); let n = 0;
    for (let e = 0; e < g.edgeCount; e++) { const nb = g.neighbor(c, r, e); if (cells()[key(nb.c, nb.r)]?.fill) n++; }
    if (n > best) { best = n; k = kk; if (n === g.edgeCount) break; }
  }
  if (!k) return null;
  const [c, r] = k.split(',').map(Number); return { c, r };
}
function setFp(on) {
  if (on && !S.fpCam) S.fpCam = fpStart();
  if (on && !S.fpCam) { toast('Paint a room first: the first-person camera walks on room cells.'); on = false; }
  S.fp = on; $('fp-toggle').checked = on; wrap.classList.toggle('fp', on); $('fp-hint').hidden = !on;
  try { localStorage.setItem('sg.fp.gm', on ? '1' : '0'); } catch { /* ignore */ }
  invalidate();
}
/* line of sight overlay: from the selected token or marker, else the runner we are seeing as */
const LOS_RADIUS = 20;
function losSource() {
  if (S.selected) {
    const { c, r } = S.selected;
    if (markerAt(c, r)) return { c, r, who: (markerAt(c, r).label || (MARKER_BY_ID[markerAt(c, r).type] || MARKER_TYPES[0]).name) };
    const p = S.ctx.players.find(q => q.currentMapId === MAP_ID && (q.state.maps || {})[MAP_ID]?.token && q.state.maps[MAP_ID].token.c === c && q.state.maps[MAP_ID].token.r === r);
    if (p) return { c, r, who: p.name };
  }
  const p = player(), t = p && pms(p).token;
  return t ? { c: t.c, r: t.r, who: p.name } : null;
}
function losField() {
  const src = S.los && losSource();
  return src ? GridCore.sightField(S.map, src, LOS_RADIUS, 'gm' + (S.geoSeq || 0)) : null;
}
function setLos(on) {
  S.los = on; $('los-toggle').checked = on; $('los-key').hidden = !on;
  try { localStorage.setItem('sg.los.gm', on ? '1' : '0'); } catch { /* ignore */ }
  if (on && !losSource()) toast('Select a token or marker (or see the map as a runner) to show what it can see.');
  requestDraw();
}
$('los-toggle').onchange = e => setLos(e.target.checked);
function fpBump() { wrap.classList.remove('bump'); void wrap.offsetWidth; wrap.classList.add('bump'); }
const fpc = FPView.controller({
  map: () => S.map, mapId: () => MAP_ID, at: () => S.fpCam, storeKey: 'sg.fp.gmface.', redraw: () => requestDraw(),
  step: cell => { const k = key(cell.c, cell.r); if (G().inBounds(cell.c, cell.r) && cells()[k] && cells()[k].fill) { S.fpCam = { c: cell.c, r: cell.r }; requestDraw(); } else fpBump(); },
  door: edge => { const at = S.fpCam; if (at && doorOnEdge(G(), cells(), at.c, at.r, edge)) toggleDoorAt(at.c, at.r, edge, false); else fpBump(); },
});
$('fp-toggle').onchange = e => setFp(e.target.checked);
function fpSprites(view) {
  const out = [], g = G(), gm = view.mode !== 'player';
  for (const m of markers()) {
    if (!gm && (m.hidden || GridCore.visibility(view, key(m.c, m.r), cells()[key(m.c, m.r)]) !== 'full')) continue;
    const p = g.cellCenter(m.c, m.r);
    out.push({ kind: 'marker', x: p.x, y: p.y, type: m.type, color: m.color, hidden: !!m.hidden, label: m.label || (MARKER_BY_ID[m.type] || MARKER_TYPES[0]).name, cm: m.cm, statuses: m.statuses, at: { c: m.c, r: m.r } });
  }
  for (const t of view.tokens || []) {
    if (!gm && GridCore.visibility(view, key(t.c, t.r), cells()[key(t.c, t.r)]) !== 'full') continue;
    if (S.fpCam && t.c === S.fpCam.c && t.r === S.fpCam.r) continue;     // whoever we are standing on
    const p = g.cellCenter(t.c, t.r);
    out.push({ kind: 'token', x: p.x, y: p.y, color: t.color, name: t.name, label: t.name, cm: t.cm, statuses: t.statuses, at: { c: t.c, r: t.r } });
  }
  return out;
}
function drawFirstPerson(dpr, W, H) {
  if (S.sceneDirty) renderSceneCache();
  const view = currentView(), cam = fpc.camera(performance.now());
  if (!cam) { setFp(false); return; }
  FPView.render(ctx2d, W, H, dpr, { map: S.map, view, cam, sprites: fpSprites(view) });
  const c = G().cellCenter(S.fpCam.c, S.fpCam.r); vp.centerOn(c.x, c.y); vp.drawMinimap(mini);
  updateStatus();
  if (cam.animating) requestDraw();
}

// ------------------------------------------------------------ accessors
const cells = () => S.map.data.cells;
const markers = () => S.map.data.markers;
const rooms = () => S.map.data.rooms;
const colors = () => S.map.settings.colors;
const G = () => geom(S.map);
const player = () => S.ctx.players.find(p => p.id === S.viewAs) || null;
function pms(p, mapId = MAP_ID) { p.state.maps = p.state.maps || {}; return p.state.maps[mapId] = p.state.maps[mapId] || { explored: {}, token: null, mapStation: false }; }
function getCell(c, r, create) { const k = key(c, r); let cell = cells()[k]; if (!cell && create) cell = cells()[k] = {}; return cell; }
function hasContent(cell) { return !!(cell && (cell.fill || (cell.doors && Object.keys(cell.doors).length))); }
function roomOf(k) { return rooms().find(rm => rm.cells.includes(k)); }
function markerAt(c, r) { return markers().find(m => m.c === c && m.r === r); }

// ------------------------------------------------------------ view model
function currentView() {
  const showRooms = S.map.settings.showRoomLabels !== false;
  if (S.mode === 'edit') return { mode: 'edit', rooms: showRooms };
  const tokens = [];
  for (const p of S.ctx.players) {
    if (p.currentMapId !== MAP_ID) continue;
    const t = (p.state.maps || {})[MAP_ID]?.token;
    if (t) tokens.push({ c: t.c, r: t.r, color: p.color, name: p.name, me: p.id === S.viewAs, cm: p.cm, statuses: p.statuses });
  }
  const p = player();
  if (!p) return { mode: 'gm', tokens, rooms: showRooms };
  const ms = pms(p);
  return { mode: 'player', explored: new Set(Object.keys(ms.explored)), mapStation: !!ms.mapStation, tokens };
}
function hoverLabel() {
  if (!S.hover) return null;
  const hs = S.hoverSprite, m = hs && hs.kind === 'marker' ? hs.m : markerAt(S.hover.c, S.hover.r), parts = [];
  if (hs && hs.kind === 'token') return { c: hs.t.c, r: hs.t.r, text: hs.t.name };
  if (m && m.label) parts.push(m.label);
  if (m && hs) return parts.length || m.linkId ? { c: m.c, r: m.r, text: parts.concat(m.linkId ? ['→ link'] : []).join(' · ') } : null;
  if (m && m.linkId) { const t = m.target && S.ctx.allMaps.find(x => x.id === m.target.mapId); parts.push('→ ' + (t ? t.name : 'by ID ' + m.linkId)); }
  const rm = roomOf(key(S.hover.c, S.hover.r));
  if (rm && S.map.settings.showRoomLabels === false) parts.push(rm.name);
  return parts.length ? { c: S.hover.c, r: S.hover.r, text: parts.join(' · ') } : null;
}

// ------------------------------------------------------------ drawing (scene cached; overlays per frame)
function invalidate() { S.sceneDirty = true; S.geoSeq = (S.geoSeq || 0) + 1; requestDraw(); }
function requestDraw() { if (!S.frame) S.frame = requestAnimationFrame(() => { S.frame = null; draw(); }); }
function renderSceneCache() {
  const pixel = false, view = currentView(), { w, h } = G().mapPixelSize();
  const q = Math.min(3, Math.max(1, Math.ceil(vp.zoom * (window.devicePixelRatio || 1))));
  const ow = Math.ceil(w * q), oh = Math.ceil(h * q);
  if (scene.width !== ow || scene.height !== oh) { scene.width = ow; scene.height = oh; }
  if (vp.iso) GridCore.buildIsoLayers(S.iso, S.map, view, q);
  else { sctx.setTransform(q, 0, 0, q, 0, 0); sctx.clearRect(0, 0, w, h); renderScene(sctx, S.map, view, { pixel }); scene._q = q; }
  const { MW, MH, scale } = vp.minimapSize();
  if (mini.width !== MW || mini.height !== MH) { mini.width = MW; mini.height = MH; }
  mctx.setTransform(scale, 0, 0, scale, 0, 0); mctx.clearRect(0, 0, w, h);
  renderScene(mctx, S.map, view, { pixel: false, grid: false, borders: false, roomNames: false, forExport: true });
  S.sceneDirty = false; S.sceneZoom = vp.zoom; S.sceneIso = vp.iso;
}
function draw() {
  if (!S.map) return;
  const dpr = window.devicePixelRatio || 1, W = wrap.clientWidth, H = wrap.clientHeight;
  if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) { canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr); }
  if (S.fp && S.fpCam) { drawFirstPerson(dpr, W, H); return; }
  const pixel = false;
  if (S.sceneDirty || Math.abs(vp.zoom - S.sceneZoom) > 0.5 || S.sceneIso !== vp.iso) renderSceneCache();
  const view = currentView();
  ctx2d.setTransform(1, 0, 0, 1, 0, 0);
  ctx2d.fillStyle = view.mode === 'edit' ? colors().background : colors().fog;
  ctx2d.fillRect(0, 0, canvas.width, canvas.height);
  ctx2d.imageSmoothingEnabled = !pixel;
  if (vp.iso) GridCore.drawIsoLayers(ctx2d, S.iso, vp, dpr, G().cs);
  else { ctx2d.setTransform(...vp.matrix(dpr)); const q = scene._q || 1; ctx2d.drawImage(scene, 0, 0, scene.width / q, scene.height / q); }
  ctx2d.setTransform(...vp.matrix(dpr));
  const lf = losField();
  if (lf) GridCore.drawSight(ctx2d, S.map, lf, vp.zoom);

  const g = G();
  ctx2d.lineWidth = 2 / vp.zoom;
  if (S.dragging && (S.dragging.kind === 'rect' || S.dragging.kind === 'room') && S.hover) {
    ctx2d.strokeStyle = colors().highlight; ctx2d.setLineDash([6 / vp.zoom, 4 / vp.zoom]);
    for (const k of dragCells()) { const [c, r] = k.split(',').map(Number); tracePoly(ctx2d, g.cellCorners(c, r), false); ctx2d.stroke(); }
    ctx2d.setLineDash([]);
  } else if (S.hover) {
    const hc = (S.tool === 'reveal' || S.tool === 'hide') ? g.brushCells(S.hover, S.brush) : [S.hover];
    ctx2d.strokeStyle = colors().highlight;
    for (const c of hc) { tracePoly(ctx2d, g.cellCorners(c.c, c.r), false); ctx2d.stroke(); }
    if ((S.tool === 'door' || S.tool === 'pdoor') && S.hoverPt) {
      const e = g.nearestEdge(S.hover.c, S.hover.r, S.hoverPt.x, S.hoverPt.y);
      const [a, b] = g.edgePoints(S.hover.c, S.hover.r, e);
      const existing = S.tool === 'pdoor' ? doorOnEdge(g, cells(), S.hover.c, S.hover.r, e) : null;
      if (S.tool === 'door' || existing) {
        ctx2d.strokeStyle = S.tool === 'door' ? $('door-color').value : colors().highlight; ctx2d.lineWidth = 4 / vp.zoom;
        ctx2d.beginPath(); ctx2d.moveTo(a.x, a.y); ctx2d.lineTo(b.x, b.y); ctx2d.stroke();
      }
    }
  }
  if (S.mode === 'edit' && S.tool === 'room') {
    ctx2d.strokeStyle = colors().roomLabel; ctx2d.lineWidth = 1.5 / vp.zoom; ctx2d.setLineDash([3 / vp.zoom, 3 / vp.zoom]);
    for (const rm of rooms()) for (const k of rm.cells) { const [c, r] = k.split(',').map(Number); tracePoly(ctx2d, g.cellCorners(c, r), false); ctx2d.stroke(); }
    ctx2d.setLineDash([]);
  }
  if (S.selected) {
    ctx2d.strokeStyle = colors().highlight; ctx2d.lineWidth = 3 / vp.zoom; ctx2d.setLineDash([4 / vp.zoom, 3 / vp.zoom]);
    tracePoly(ctx2d, g.cellCorners(S.selected.c, S.selected.r), false); ctx2d.stroke(); ctx2d.setLineDash([]);
  }
  // player pings (last 10 s)
  if (S.mode === 'play') {
    const nowS = Date.now() / 1000; let active = false;
    for (const p of S.ctx.players) {
      const pg = p.ping; if (!pg || pg.mapId !== MAP_ID) continue;
      const age = nowS - (S.clockSkew || 0) - pg.t; if (age < 0 || age > 10) continue;
      active = true; const { x, y } = g.cellCenter(pg.c, pg.r); drawPing(ctx2d, x, y, g.cs, p.color, age);
    }
    if (active && !S.pingFrame) S.pingFrame = setTimeout(() => { S.pingFrame = null; requestDraw(); }, 60);
  }
  // ---- screen space: upright sprites (iso), dragged marker, hover label
  ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0);
  if (vp.iso) GridCore.renderSprites(ctx2d, S.map, view, vp, { roomNames: view.rooms });
  if (S.dragging && S.dragging.kind === 'marker' && S.dragging.moved && S.hover) {
    const c0 = g.cellCenter(S.hover.c, S.hover.r), p = vp.toScreen(c0.x, c0.y), d = g.cs * vp.zoom * 0.62;
    ctx2d.globalAlpha = 0.6; drawMarker(ctx2d, p.x, p.y - (vp.iso ? d * 0.55 : 0), d, S.dragging.m.type, S.dragging.m.color || colors().markerDefault, colors().markerText, false); ctx2d.globalAlpha = 1;
  }
  const hl = hoverLabel();
  if (hl) { const c0 = g.cellCenter(hl.c, hl.r), p = vp.toScreen(c0.x, c0.y); GridCore.drawLabel(ctx2d, p.x, p.y + g.cs * vp.zoom * 0.35, hl.text, g.cs * vp.zoom); }
  vp.drawMinimap(mini);
  updateStatus();
}
function updateStatus() {
  const g = G(), c = S.hover;
  $('st-cell').textContent = c ? `Cell ${c.c}, ${c.r}` : '–';
  const rm = c && roomOf(key(c.c, c.r)); $('st-room').textContent = rm ? `Room: ${rm.name}` : '';
  const m = c && markerAt(c.c, c.r);
  $('st-marker').textContent = m ? `${(MARKER_BY_ID[m.type] || MARKER_TYPES[0]).name}${m.label ? ': ' + m.label : ''}${m.linkId ? ' → link ' + m.linkId : ''}${m.hidden ? ' (hidden)' : ''}` : '';
  let doorTxt = '';
  if (c && S.hoverPt) { const e = g.nearestEdge(c.c, c.r, S.hoverPt.x, S.hoverPt.y), d = doorOnEdge(g, cells(), c.c, c.r, e); if (d) doorTxt = `${g.edgeNames[e]} door: ${d.locked ? 'locked' : d.open ? 'open' : 'closed'}`; }
  $('st-door').textContent = doorTxt;
  let losTxt = '';
  const lf = c && losField();
  if (lf && (c.c !== lf.from.c || c.r !== lf.from.r)) {
    const k = key(c.c, c.r), who = losSource().who;
    if (lf.seen.has(k)) { const cv = lf.seen.get(k); losTxt = cv ? `${who}: Cover ${GridCore.COVER_NAMES[cv]}` : `${who}: in plain sight`; }
    else if (lf.hidden.has(k)) losTxt = `${who}: out of sight`;
  }
  $('st-los').textContent = losTxt;
}
function dragCells() {
  if (S.dragging.kind === 'room') return [...S.dragging.set];
  const a = S.dragging.start, b = S.hover, out = [];
  for (let c = Math.min(a.c, b.c); c <= Math.max(a.c, b.c); c++) for (let r = Math.min(a.r, b.r); r <= Math.max(a.r, b.r); r++) out.push(key(c, r));
  return out;
}

// ------------------------------------------------------------ undo (edit mode)
const UNDO = [];
function pushUndo() { UNDO.push(JSON.stringify(S.map.data)); if (UNDO.length > 40) UNDO.shift(); }
function undo() {
  if (S.mode !== 'edit' || !UNDO.length) { toast('Nothing to undo.'); return; }
  S.map.data = JSON.parse(UNDO.pop());
  S.rt.all = true;
  markDirty(); renderRoomList(); renderRoomSelects(); renderLegend(); if (S.selected) renderInspector();
}

// ------------------------------------------------------------ persistence (map)
function markDirty() {
  S.dirty = true; $('save-state').textContent = 'Unsaved';
  clearTimeout(S.saveTimer); S.saveTimer = setTimeout(saveMap, 700);
  invalidate();
}
async function saveMap() {
  if (!S.map || S.deleted) return;
  $('save-state').textContent = 'Saving…';
  try {
    const runtime = S.rt.all ? { doors: allDoorKeys(), markers: markers().map(m => m.id) } : { doors: [...S.rt.doors], markers: [...S.rt.markers] };
    const sent = { doors: new Set(S.rt.doors), markers: new Set(S.rt.markers), all: S.rt.all };
    await api(`/api/maps/${MAP_ID}`, 'PUT', { name: S.map.name, width: S.map.width, height: S.map.height, cellSize: S.map.cellSize, settings: S.map.settings, data: S.map.data, campaignId: S.map.campaignId, runtime });
    for (const k of sent.doors) S.rt.doors.delete(k);
    for (const k of sent.markers) S.rt.markers.delete(k);
    if (sent.all) S.rt.all = false;
    S.dirty = false; $('save-state').textContent = 'Saved';
  } catch (e) { $('save-state').textContent = 'Save failed, retrying'; S.saveTimer = setTimeout(saveMap, 3000); }
}

// ------------------------------------------------------------ fog (delta updates; never overwrite a player's whole state)
function queueFog(action, keys) {
  const p = player(); if (!p) return;
  const ms = pms(p);
  for (const k of keys) { if (!cells()[k]) continue; if (action === 'reveal') ms.explored[k] = true; else delete ms.explored[k]; }
  if (!S.fogQueue || S.fogQueue.action !== action || S.fogQueue.pid !== p.id) { flushFog(); S.fogQueue = { action, pid: p.id, keys: new Set() }; }
  for (const k of keys) S.fogQueue.keys.add(k);
  clearTimeout(S.fogTimer); S.fogTimer = setTimeout(flushFog, 350);
  invalidate();
}
async function flushFog() {
  clearTimeout(S.fogTimer);
  const q = S.fogQueue; S.fogQueue = null;
  if (!q || !q.keys.size) return;
  try { const r = await api(`/api/maps/${MAP_ID}/reveal`, 'POST', { players: [q.pid], cells: [...q.keys], action: q.action }); mergePlayers(r.players); }
  catch (e) { toast('Fog update failed: ' + e.message); }
}
async function fogAction(players, cellKeys, action, msg) {
  try { const r = await api(`/api/maps/${MAP_ID}/reveal`, 'POST', { players, cells: cellKeys, action }); mergePlayers(r.players); if (msg) toast(msg); }
  catch (e) { toast(e.message); }
}
function mergePlayers(list) {
  for (const np of list) { if (S.fogQueue && S.fogQueue.pid === np.id) continue; const lp = S.ctx.players.find(p => p.id === np.id); if (lp) Object.assign(lp, np); else S.ctx.players.push(np); }
  renderPlayers(); renderLegend(); invalidate();
  if (S.selected) renderInspector();
}
async function placeToken(p, c, r) {
  const cell = getCell(c, r);
  if (!cell || !cell.fill) { toast('Tokens can only stand on painted cells.'); return; }
  try { const updated = await api(`/api/players/${p.id}/place`, 'POST', { mapId: MAP_ID, c, r }); mergePlayers([updated]); }
  catch (e) { toast(e.message); }
}
async function moveMarker(m, c, r) {
  if (markerAt(c, r)) { toast('That cell already has a marker.'); return; }
  if (S.mode === 'edit') { pushUndo(); m.c = c; m.r = r; markDirty(); renderLegend(); return; }
  const from = { c: m.c, r: m.r }; m.c = c; m.r = r; invalidate();
  try { await api(`/api/maps/${MAP_ID}/marker`, 'POST', { id: m.id, c, r }); } catch (e) { m.c = from.c; m.r = from.r; invalidate(); toast(e.message); }
}
async function updateMarkerLive(m, fields) {
  Object.assign(m, fields);
  if (fields.cm === null) delete m.cm;
  if (fields.statuses === null) delete m.statuses;
  invalidate();
  if (S.mode === 'edit') { if ('cm' in fields || 'statuses' in fields) S.rt.markers.add(m.id); markDirty(); return; }
  try { const r = await api(`/api/maps/${MAP_ID}/marker`, 'POST', { id: m.id, ...fields }); if (r.marker.cm) m.cm = r.marker.cm; } catch (e) { toast(e.message); }
}
async function toggleDoorAt(c, r, e, lock) {
  const d = doorOnEdge(G(), cells(), c, r, e);
  if (!d) return;
  const before = { open: d.open, locked: !!d.locked };
  if (lock) { d.locked = !d.locked; if (d.locked) d.open = false; }
  else if (d.locked) { toast('That door is locked. Shift+click to unlock it.'); return; }
  else d.open = !d.open;
  invalidate();
  if (S.mode === 'edit') { S.rt.doors.add(doorKey(c, r, e)); markDirty(); if (S.selected) renderInspector(); return; }
  try { const res = await api(`/api/maps/${MAP_ID}/door`, 'POST', lock ? { c, r, edge: e, locked: d.locked } : { c, r, edge: e, open: d.open }); d.open = res.open; d.locked = res.locked; }
  catch (err) { Object.assign(d, before); toast(err.message); }
  invalidate(); if (S.selected) renderInspector();
}
/* doors are stored on one of the two cells of an edge: "c,r:edge" of the owning cell */
function doorKey(c, r, e) {
  const own = (getCell(c, r) || {}).doors;
  if (own && own[e]) return `${key(c, r)}:${e}`;
  const g = G(), n = g.neighbor(c, r, e), opp = g.hex ? (e + 3) % 6 : (e + 2) % 4;
  return `${key(n.c, n.r)}:${opp}`;
}
function allDoorKeys() { const out = []; for (const k in cells()) for (const e in (cells()[k].doors || {})) out.push(`${k}:${e}`); return out; }
function revealAll(val) {
  const p = player(); if (!p) return;
  confirmDialog(val ? `Reveal the whole map for ${p.name}? Secret cells included.` : `Hide everything from ${p.name}? Their token stays where it is.`,
    () => fogAction([p.id], 'all', val ? 'reveal' : 'hide'));
}
function revealAllEveryone(val) {
  if (!S.ctx.players.length) { toast('No runners in this game yet.'); return; }
  confirmDialog(val ? 'Reveal the whole map for every player? Secret cells included.' : 'Hide everything from every player?',
    () => fogAction('all', 'all', val ? 'reveal' : 'hide', val ? 'Map revealed for everyone.' : 'Map hidden from everyone.'));
}

// ------------------------------------------------------------ edit actions
function paintCell(c, r) { const cell = getCell(c, r, true); cell.fill = $('paint-color').value; cell.border = $('paint-border').value; cell.borderOn = $('paint-border-on').checked; }
function eraseCell(c, r) {
  const k = key(c, r); if (!cells()[k]) return;
  delete cells()[k];
  S.map.data.markers = markers().filter(m => !(m.c === c && m.r === r));
  for (const rm of rooms()) rm.cells = rm.cells.filter(x => x !== k);
  S.map.data.rooms = rooms().filter(rm => rm.cells.length);
}
function toggleSecret(c, r) { const cell = getCell(c, r, true); cell.secret = !cell.secret; if (!hasContent(cell) && !cell.secret) delete cells()[key(c, r)]; }
function toggleDoor(c, r, e) {
  const g = G(), n = g.neighbor(c, r, e), opp = g.hex ? (e + 3) % 6 : (e + 2) % 4, nb = getCell(n.c, n.r);
  if (nb && nb.doors && nb.doors[opp] && !((getCell(c, r) || {}).doors || {})[e]) { c = n.c; r = n.r; e = opp; }   // the door lives on the other side of this edge
  const cell = getCell(c, r, true); cell.doors = cell.doors || {};
  const color = $('door-color').value;
  if (cell.doors[e] && cell.doors[e].color === color) delete cell.doors[e]; else cell.doors[e] = { color, open: false };
  if (!Object.keys(cell.doors).length) delete cell.doors;
  if (!hasContent(cell) && !cell.secret) delete cells()[key(c, r)];
}
function placeMarker(c, r) {
  if (markerAt(c, r)) { S.selected = { c, r }; renderInspector(); return; }
  const m = { id: Math.random().toString(36).slice(2, 10), c, r, type: S.markerType, color: $('marker-color').value, label: $('marker-label').value.trim() };
  const cm = cmFromAttrs(+$('marker-body').value, +$('marker-wil').value);
  if (cm) m.cm = cm;
  if (S.templateNpc) { m.npc = JSON.parse(JSON.stringify(S.templateNpc.npc)); m.cm = JSON.parse(JSON.stringify(S.templateNpc.cm)); if (!m.label) m.label = S.templateNpc.npc.template; }
  if ($('link-on').checked) {
    if (!$('link-map').value) { toast('Pick a destination map first.'); return; }
    m.target = { mapId: $('link-map').value, c: +$('link-c').value || 0, r: +$('link-r').value || 0 };
    m.linkId = ($('link-id').value.trim().replace(/[^A-Za-z0-9_-]/g, '') || newLinkId()).slice(0, 24);
    if ($('link-return').checked) {
      saveMap().then(() => api(`/api/maps/${m.target.mapId}/return-link`, 'POST', { c: m.target.c, r: m.target.r, linkId: m.linkId, color: m.color, label: m.label, type: m.type, fromMapId: MAP_ID, fromC: c, fromR: r }))
        .then(() => toast(`Return link created on the other map (ID ${m.linkId}).`)).catch(e => toast('Return link: ' + e.message));
    }
    $('link-id').value = newLinkId();
  }
  markers().push(m);
}
function cmFromAttrs(body, wil) {
  if (!(body > 0) && !(wil > 0)) return null;
  return { pm: body > 0 ? 8 + Math.ceil(body / 2) : 0, sm: wil > 0 ? 8 + Math.ceil(wil / 2) : 0, ov: body > 0 ? body * 2 : 0, p: 0, s: 0 };
}
/* NPC template for new markers (fetched once, copied into each marker) */
/* NPC templates by kind, plus the runners' own vehicles (linked: damage is shared with their sheet) */
const KIND_LABEL = { Grunt: 'Grunts (Professional Rating)', Spirit: 'Spirits (pick a Force)', IC: 'IC (pick the host rating)', Vehicle: 'Vehicles', Drone: 'Drones' };
function allTemplates() { return [...SR.CAT.npcTemplates, ...((S.ctx && S.ctx.vehicles) || [])]; }
function templateGroups(sel) {
  const groups = {};
  for (const t of allTemplates()) (groups[t.kind] = groups[t.kind] || []).push(t);
  for (const [k, list] of Object.entries(groups)) sel.append(h('optgroup', { label: KIND_LABEL[k] || (k.endsWith('s') ? k : k + 's') }, list.map(t => option(t.key, t.pr != null ? `PR ${t.pr} · ${t.name}` : t.name))));
}
function renderTemplateSelect() {
  const sel = $('marker-template');
  const keep = sel.value;
  while (sel.options.length > 1 || sel.querySelector('optgroup')) { const g = sel.querySelector('optgroup'); if (!g) break; g.remove(); }
  templateGroups(sel);
  sel.value = keep;
}
async function loadTemplate() {
  const k = $('marker-template').value;
  const t = allTemplates().find(x => x.key === k);
  $('marker-force-wrap').hidden = !(t && t.force);
  $('marker-force-label').textContent = t && t.forceLabel ? t.forceLabel : 'Spirit Force';
  if (!k) { S.templateNpc = null; cmHint(); return; }
  try { S.templateNpc = await api(`/api/npc-templates/${encodeURIComponent(k)}?force=${+$('marker-force').value || 3}`); cmHint(); }
  catch (e) { toast(e.message); }
}
$('marker-template').onchange = loadTemplate;
$('marker-force').onchange = loadTemplate;
function cmHint() {
  if (S.templateNpc) { const n = S.templateNpc.npc, cm = S.templateNpc.cm; $('marker-cm-hint').textContent = `New markers are ${n.template}: ${cm.grunt ? cm.pm + ' boxes (grunt)' : cm.pm + ' Physical, ' + cm.sm + ' Stun'}, DR ${n.dr}, init ${n.init} + ${n.init_dice}D6.`; return; }
  const cm = cmFromAttrs(+$('marker-body').value, +$('marker-wil').value);
  $('marker-cm-hint').textContent = cm ? `New markers get ${cm.pm ? cm.pm + ' Physical' : ''}${cm.pm && cm.sm ? ' and ' : ''}${cm.sm ? cm.sm + ' Stun' : ''} boxes${cm.ov ? ` (+${cm.ov} overflow)` : ''}.` : 'Leave empty for markers without a condition monitor.';
}
$('marker-body').oninput = cmHint; $('marker-wil').oninput = cmHint;
function newLinkId() { return 'L' + Math.random().toString(36).slice(2, 7).toUpperCase(); }
$('link-newid').onclick = () => { $('link-id').value = newLinkId(); };
function finishRoom(set) {
  const keys = [...set].filter(k => cells()[k] && cells()[k].fill);
  if (!keys.length) return;
  const name = $('room-name').value.trim() || `Room ${rooms().length + 1}`;
  for (const rm of rooms()) rm.cells = rm.cells.filter(k => !set.has(k));
  S.map.data.rooms = rooms().filter(rm => rm.cells.length);
  rooms().push({ id: Math.random().toString(36).slice(2, 10), name, cells: keys });
  $('room-name').value = '';
  renderRoomList(); renderRoomSelects();
}

// ------------------------------------------------------------ tool dispatch
function needPlayer() { const p = player(); if (!p) toast('Pick a player under "Viewing as" first.'); return p; }
function applyTool(cell, pt, isFirst) {
  const { c, r } = cell;
  switch (S.tool) {
    case 'paint': if (isFirst) pushUndo(); paintCell(c, r); break;
    case 'erase': if (isFirst) pushUndo(); eraseCell(c, r); break;
    case 'secret': if (!isFirst) return; pushUndo(); toggleSecret(c, r); break;
    case 'door': if (!isFirst) return; pushUndo(); toggleDoor(c, r, G().nearestEdge(c, r, pt.x, pt.y)); break;
    case 'marker': if (!isFirst) return; if (markerAt(c, r)) { S.selected = { c, r }; renderInspector(); return; } pushUndo(); placeMarker(c, r); break;
    case 'pmarker': if (!isFirst) return; S.selected = { c, r }; renderInspector(); return;
    case 'select': S.selected = { c, r }; renderInspector(); requestDraw(); return;
    case 'reveal': if (!needPlayer()) return; queueFog('reveal', G().brushCells(cell, S.brush).map(b => key(b.c, b.r))); return;
    case 'hide': if (!needPlayer()) return; queueFog('hide', G().brushCells(cell, S.brush).map(b => key(b.c, b.r))); return;
    case 'pdoor': if (!isFirst) return; toggleDoorAt(c, r, G().nearestEdge(c, r, pt.x, pt.y), S.shiftDown); return;
    case 'token': if (!isFirst) return; { const p = needPlayer(); if (p) placeToken(p, c, r); } return;
    default: return;
  }
  markDirty();
  if (S.selected && S.selected.c === c && S.selected.r === r) renderInspector();
  renderLegend();
}

// ------------------------------------------------------------ pointer
canvas.addEventListener('contextmenu', e => e.preventDefault());
canvas.addEventListener('pointerdown', ev => {
  canvas.setPointerCapture(ev.pointerId);
  const { sx, sy } = vp.canvasPoint(ev);
  if (S.fp && S.fpCam) {
    if (ev.button !== 0) return;
    const hit = FPView.pick(sx, sy);
    if (hit) { S.selected = hit.at; renderInspector(); requestDraw(); }
    else fpc.tap(sx, sy, wrap.clientWidth, wrap.clientHeight);
    return;
  }
  if (ev.button === 1 || ev.button === 2 || S.spaceDown) { S.dragging = { kind: 'pan', sx, sy, px: vp.panX, py: vp.panY }; canvas.classList.add('panning'); return; }
  if (ev.button !== 0) return;
  const pt = vp.screenToMap(sx, sy);
  let cell = G().pointToCell(pt.x, pt.y);
  // in the isometric view, markers and tokens stand above their cell: hit the drawn icon
  const sprite = GridCore.pickSprite(S.map, currentView(), vp, sx, sy);
  const hitMarker = sprite && sprite.kind === 'marker' ? sprite.m : (cell && markerAt(cell.c, cell.r));
  const grabsMarkers = S.tool === 'marker' || S.tool === 'pmarker' || S.tool === 'select'
    || (S.mode === 'play' && !S.viewAs && (S.tool === 'reveal' || S.tool === 'hide'));
  if (grabsMarkers && hitMarker) { S.dragging = { kind: 'marker', m: hitMarker, from: { c: hitMarker.c, r: hitMarker.r }, moved: false }; return; }
  if (sprite && S.tool === 'select') cell = sprite.kind === 'marker' ? { c: sprite.m.c, r: sprite.m.r } : { c: sprite.t.c, r: sprite.t.r };
  if (S.tool === 'rect') { if (cell) { pushUndo(); S.dragging = { kind: 'rect', start: cell }; } return; }
  if (S.tool === 'room') { if (cell) { pushUndo(); S.dragging = { kind: 'room', start: cell, set: new Set([key(cell.c, cell.r)]) }; } requestDraw(); return; }
  S.shiftDown = ev.shiftKey;
  S.dragging = { kind: 'apply', last: null };
  if (cell) { applyTool(cell, pt, true); S.dragging.last = key(cell.c, cell.r); }
  requestDraw();
});
canvas.addEventListener('pointermove', ev => {
  const { sx, sy } = vp.canvasPoint(ev), pt = vp.screenToMap(sx, sy);
  if (S.fp && S.fpCam) { canvas.style.cursor = FPView.pick(sx, sy) ? 'pointer' : ''; return; }
  S.hoverPt = pt; S.hover = G().pointToCell(pt.x, pt.y);
  S.hoverSprite = S.dragging ? null : GridCore.pickSprite(S.map, currentView(), vp, sx, sy);
  if (S.dragging) {
    if (S.dragging.kind === 'pan') { vp.panX = S.dragging.px + (sx - S.dragging.sx); vp.panY = S.dragging.py + (sy - S.dragging.sy); }
    else if (S.dragging.kind === 'apply' && S.hover) { const k = key(S.hover.c, S.hover.r); if (k !== S.dragging.last) { applyTool(S.hover, pt, false); S.dragging.last = k; } }
    else if (S.dragging.kind === 'room' && S.hover) S.dragging.set.add(key(S.hover.c, S.hover.r));
    else if (S.dragging.kind === 'marker' && S.hover && (S.hover.c !== S.dragging.from.c || S.hover.r !== S.dragging.from.r)) S.dragging.moved = true;
  }
  requestDraw();
});
function endDrag() {
  if (!S.dragging) return;
  if (S.dragging.kind === 'rect' && S.hover) { for (const k of dragCells()) { const [c, r] = k.split(',').map(Number); paintCell(c, r); } markDirty(); renderLegend(); }
  if (S.dragging.kind === 'room') { finishRoom(S.dragging.set); markDirty(); }
  if (S.dragging.kind === 'apply') flushFog();
  if (S.dragging.kind === 'marker') {
    if (S.dragging.moved && S.hover) moveMarker(S.dragging.m, S.hover.c, S.hover.r);
    else { S.selected = S.dragging.from; renderInspector(); }
  }
  S.dragging = null; canvas.classList.remove('panning'); requestDraw();
}
canvas.addEventListener('pointerup', endDrag);
canvas.addEventListener('pointercancel', endDrag);
canvas.addEventListener('pointerleave', () => { S.hover = null; requestDraw(); });
canvas.addEventListener('wheel', ev => { ev.preventDefault(); if (S.fp) return; const { sx, sy } = vp.canvasPoint(ev); vp.zoomAt(sx, sy, Math.exp(-ev.deltaY * 0.0015)); requestDraw(); }, { passive: false });

// ------------------------------------------------------------ keyboard
const TOOL_KEYS = { edit: { p: 'paint', r: 'rect', e: 'erase', s: 'secret', d: 'door', m: 'marker', g: 'room', v: 'select' },
                    play: { p: 'reveal', e: 'hide', d: 'pdoor', t: 'token', m: 'pmarker', v: 'select' } };
window.addEventListener('keydown', ev => {
  if (ev.target.matches('input, textarea, select, [contenteditable]') || document.querySelector('dialog[open]')) return;
  if (ev.code === 'Space') { S.spaceDown = true; canvas.classList.add('panning'); ev.preventDefault(); return; }
  const k = ev.key.toLowerCase();
  if ((ev.ctrlKey || ev.metaKey) && k === 'z') { ev.preventDefault(); undo(); return; }
  if (ev.ctrlKey || ev.metaKey) return;
  if (k === '3') { setFp(!S.fp); return; }
  if (k === 'l' && !S.fp) { setLos(!S.los); return; }
  if (S.fp && S.fpCam && !ev.altKey) { if (k === 'escape') { setFp(false); return; } if (fpc.key(ev)) return; }
  if (k === 'f') { vp.fit(); invalidate(); return; }
  if (k === 'i') { setIso(!vp.iso); return; }
  if (k === 'escape') { S.selected = null; renderInspector(); requestDraw(); return; }
  if (k === 'tab' && S.mode === 'play' && S.ctx.players.length) { ev.preventDefault(); const ids = ['', ...S.ctx.players.map(p => p.id)]; setViewAs(ids[(ids.indexOf(S.viewAs) + 1) % ids.length]); return; }
  const t = TOOL_KEYS[S.mode][k]; if (t) setTool(t);
});
window.addEventListener('keyup', ev => { if (ev.code === 'Space') { S.spaceDown = false; if (!S.dragging) canvas.classList.remove('panning'); } });

// ------------------------------------------------------------ tool / mode UI
function setTool(t) {
  S.tool = t;
  document.querySelectorAll('.tool-group[data-mode] .tool').forEach(b => b.classList.toggle('active', b.dataset.tool === t && b.closest('.tool-group').dataset.mode === S.mode));
  document.querySelectorAll('.tool-opts').forEach(o => o.classList.toggle('visible', o.dataset.for.split(' ').includes(t)));
  requestDraw();
}
document.querySelectorAll('.tool-group[data-mode] .tool').forEach(b => b.onclick = () => setTool(b.dataset.tool));
function setMode(m) {
  flushFog();
  S.mode = m;
  $('mode-edit').classList.toggle('active', m === 'edit'); $('mode-play').classList.toggle('active', m === 'play');
  document.querySelectorAll('[data-mode]').forEach(g => { if (!g.classList.contains('dock')) g.hidden = g.dataset.mode !== m; });
  document.body.dataset.uiMode = m;
  setTool(m === 'edit' ? 'paint' : 'select');
  if (isoPref(m) !== vp.iso) setIso(isoPref(m), false);
  if (m === 'play') $('pane-selected').appendChild($('inspector'));
  else document.querySelector('.tool-group[data-mode="edit"]').appendChild($('inspector'));
  Layout.refresh(); Layout.relayout();
  S.selected = null;
  renderInspector(); renderPlayers(); renderLegend(); renderCombat(); invalidate();
  schedulePoll(m === 'play' ? 1500 : 6000);
}
$('mode-edit').onclick = () => setMode('edit');
$('mode-play').onclick = () => setMode('play');
function setViewAs(id) { flushFog(); S.viewAs = id; if (S.fp) { const p = player(), t = p && pms(p).token; if (t) S.fpCam = { c: t.c, r: t.r }; } renderViewAs(); renderPlayers(); refreshFogPanel(); renderInspector(); renderLegend(); invalidate(); }
function renderViewAs() {
  const el = $('view-as'); el.innerHTML = '';
  const mk = (id, label, color) => {
    const b = document.createElement('button'); b.className = 'pill' + (S.viewAs === id ? ' active' : '');
    b.title = id ? 'Click again to jump to their token' : 'Everything, all tokens';
    b.onclick = () => {
      if (S.viewAs === id && id) { const t = pms(player()).token; if (t) { const c = G().cellCenter(t.c, t.r); vp.centerOn(c.x, c.y); requestDraw(); } return; }
      setViewAs(id);
    };
    if (color) { const d = document.createElement('span'); d.className = 'dot'; d.style.background = color; b.appendChild(d); }
    b.appendChild(document.createTextNode(label)); el.appendChild(b);
  };
  mk('', 'GM view');
  for (const p of S.ctx.players) mk(p.id, p.name, p.color);
}
function refreshFogPanel() {
  const p = player();
  $('fog-player').hidden = !p;
  $('reveal-hint').textContent = p ? `Drag to change what ${p.name} has explored.` : 'Pick a player under “See the map as” (or See as on the Runners tab) to reveal or hide what they’ve explored. In the GM view, drag markers to move them.';
  if (p) { $('fog-player-name').textContent = p.name; $('map-station').checked = !!pms(p).mapStation; }
  renderRoomSelects();
}
$('brush-size').oninput = e => { S.brush = +e.target.value; $('brush-size-val').textContent = S.brush; requestDraw(); };
$('follow-player').onchange = e => { S.follow = e.target.checked; };
$('map-station').onchange = e => { const p = player(); if (!p) return; pms(p).mapStation = e.target.checked; invalidate(); fogAction([p.id], 'all', e.target.checked ? 'station_on' : 'station_off'); };
$('btn-reveal-all').onclick = () => revealAll(true);
$('btn-hide-all').onclick = () => revealAll(false);
$('btn-reveal-all-everyone').onclick = () => revealAllEveryone(true);
$('btn-hide-all-everyone').onclick = () => revealAllEveryone(false);
$('room-reveal').onchange = e => { const rm = rooms().find(x => x.id === e.target.value), p = player(); e.target.value = ''; if (rm && p) fogAction([p.id], rm.cells, 'reveal', `${rm.name} revealed for ${p.name}.`); };
$('room-reveal-everyone').onchange = e => { const rm = rooms().find(x => x.id === e.target.value); e.target.value = ''; if (rm) fogAction('all', rm.cells, 'reveal', `${rm.name} revealed for everyone.`); };
$('legend-toggle').onchange = e => { S.map.settings.legendVisible = e.target.checked; markDirty(); renderLegend(); };
$('rooms-toggle').onchange = e => { S.map.settings.showRoomLabels = e.target.checked; markDirty(); };
$('map-name').onchange = e => { S.map.name = e.target.value.trim() || 'Untitled map'; document.title = S.map.name + ' · ShadowGrid'; markDirty(); };
function confirmDialog(text, onOk) {
  const d = $('confirm-dialog'); $('confirm-text').textContent = text; d.returnValue = '';
  d.onclose = () => { if (d.returnValue === 'ok') onOk(); };
  d.showModal();
}

// ------------------------------------------------------------ swatches & marker picker
const RECENT_KEY = 'sg.recentColors';
function loadRecent() { try { return JSON.parse(localStorage.getItem(RECENT_KEY)) || []; } catch { return []; } }
function pushRecent(color) { localStorage.setItem(RECENT_KEY, JSON.stringify([color, ...loadRecent().filter(c => c !== color)].slice(0, 10))); renderPaintSwatches(); }
function swatchButton(c, active, onClick) { const b = document.createElement('button'); b.className = 'swatch' + (active ? ' active' : ''); b.style.background = c; b.title = c; b.onclick = onClick; return b; }
function renderPaintSwatches() {
  const el = $('paint-swatches'); el.innerHTML = '';
  const base = [colors().cellDefault, '#24414a', '#3b2a4f', '#4a1f35', '#1f3d2e', '#4a3a1c', '#2a3340', '#5a1d2c'];
  for (const c of [...new Set([...loadRecent(), ...base])].slice(0, 14)) el.appendChild(swatchButton(c, c === $('paint-color').value, () => { $('paint-color').value = c; renderPaintSwatches(); }));
}
$('paint-color').onchange = e => pushRecent(e.target.value);
function renderDoorSwatches() {
  const el = $('door-swatches'); el.innerHTML = '';
  for (const c of S.map.settings.doorPalette) el.appendChild(swatchButton(c, c === $('door-color').value, () => { $('door-color').value = c; renderDoorSwatches(); requestDraw(); }));
}
function renderMarkerTypes() {
  const el = $('marker-types'); el.innerHTML = '';
  for (const t of MARKER_TYPES) {
    const b = document.createElement('button'); b.className = t.id === S.markerType ? 'active' : ''; b.title = t.name;
    const cv = document.createElement('canvas'); cv.width = 44; cv.height = 44;
    drawMarker(cv.getContext('2d'), 22, 22, 30, t.id, $('marker-color').value, colors().markerText, false);
    b.appendChild(cv);
    const sp = document.createElement('span'); sp.textContent = t.name.split(' /')[0]; b.appendChild(sp);
    b.onclick = () => { S.markerType = t.id; renderMarkerTypes(); };
    el.appendChild(b);
  }
}
$('link-on').onchange = e => { $('link-opts').hidden = !e.target.checked; };
$('marker-color').oninput = renderMarkerTypes;
function renderLinkMaps() {
  const sel = $('link-map'); sel.innerHTML = '';
  for (const m of (S.ctx.campaign ? S.ctx.campaignMaps : S.ctx.allMaps)) { if (m.id === MAP_ID) continue; const o = document.createElement('option'); o.value = m.id; o.textContent = m.name; sel.appendChild(o); }
  if (!sel.options.length) { const o = document.createElement('option'); o.value = ''; o.textContent = 'No other maps yet'; sel.appendChild(o); }
}

// ------------------------------------------------------------ rooms UI
function renderRoomList() {
  const el = $('room-list'); el.innerHTML = '';
  for (const rm of rooms()) {
    const row = document.createElement('div'); row.className = 'mini-row';
    const inp = document.createElement('input'); inp.value = rm.name; inp.title = `${rm.cells.length} cells`;
    inp.onchange = () => { rm.name = inp.value.trim() || rm.name; markDirty(); renderRoomSelects(); };
    const go = document.createElement('button'); go.textContent = 'Find'; go.className = 'small';
    go.onclick = () => { const c = G().centroid(rm.cells); if (c) { vp.centerOn(c.x, c.y); requestDraw(); } };
    const del = document.createElement('button'); del.textContent = '✕'; del.className = 'small danger'; del.title = 'Remove room';
    del.onclick = () => { S.map.data.rooms = rooms().filter(x => x !== rm); markDirty(); renderRoomList(); renderRoomSelects(); };
    row.append(inp, go, del); el.appendChild(row);
  }
  if (!rooms().length) el.innerHTML = '<p class="hint">No rooms yet.</p>';
}
function renderRoomSelects() {
  const p = player();
  for (const [id, forPlayer] of [['room-reveal', true], ['room-reveal-everyone', false]]) {
    const sel = $(id); sel.innerHTML = '<option value="">Reveal a room…</option>';
    for (const rm of rooms()) {
      const o = document.createElement('option'); o.value = rm.id;
      const seen = forPlayer && p ? ` (${rm.cells.filter(k => pms(p).explored[k]).length}/${rm.cells.length})` : '';
      o.textContent = rm.name + seen; sel.appendChild(o);
    }
    sel.disabled = !rooms().length;
  }
}

// ------------------------------------------------------------ players UI (only rebuilt when something changed)
function renderPlayers() {
  const hasCampaign = !!S.ctx.campaign;
  $('no-campaign').hidden = hasCampaign; $('players-panel').hidden = !hasCampaign; $('snapshots-panel').hidden = !hasCampaign;
  $('dice-panel').hidden = !hasCampaign || S.mode !== 'play';
  $('tab-runners').hidden = !hasCampaign;
  Layout.refresh();
  if (S.viewAs && !S.ctx.players.some(p => p.id === S.viewAs)) S.viewAs = '';
  renderViewAs(); refreshFogPanel();
  const sig = JSON.stringify([S.viewAs, S.ctx.players.map(p => [p.id, p.name, p.color, p.radius, p.currentMapId, p.cm, p.edge, p.status, p.statuses])]);
  const typing = document.activeElement && $('player-list').contains(document.activeElement) && /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName);
  if (sig === S.playersSig || typing) return;
  S.playersSig = sig;
  const el = $('player-list'); el.innerHTML = '';
  for (const p of S.ctx.players) {
    const sw = h('input', { type: 'color', value: p.color, title: 'Token color',
      onchange: () => { p.color = sw.value; api(`/api/players/${p.id}`, 'PUT', { color: p.color }); renderViewAs(); invalidate(); } });
    const rad = h('input.radius', { type: 'number', min: 0, max: 20, value: p.radius, title: 'View radius (cells)',
      onchange: () => { p.radius = +rad.value; api(`/api/players/${p.id}`, 'PUT', { radius: p.radius }); } });
    const here = p.currentMapId === MAP_ID, elsewhere = p.currentMapId && S.ctx.allMaps.find(m => m.id === p.currentMapId);
    const cmLine = h('div.cmline', h('span', { style: { color: 'var(--phys)' } }, `P ${Math.min(p.cm.p, p.cm.pm)}/${p.cm.pm}`), h('span', { style: { color: 'var(--stun)' } }, `S ${p.cm.s}/${p.cm.sm}`),
      SR.healthTag(p.cm.status), h('span.grow'), SR.pips(p.edge.cur, p.edge.max));
    const stLine = statusEditor(p.statuses || {}, (name, on, value) => setStatus({ kind: 'player', id: p.id }, name, on, value));
    el.append(h('div.player-row',
      h('div.row.tight', { style: { flexWrap: 'nowrap' } }, sw, h('a.grow', { href: `/game/${S.ctx.campaign.id}/sheet/${p.id}`, target: '_blank', title: 'Open the character sheet' }, p.name), rad),
      p.status !== 'approved' ? h('div', SR.statusTag(p.status)) : null,
      cmLine, stLine,
      here ? h('div.row.tight', h('button.small', { type: 'button', onclick: () => attackDialog({ kind: 'player', id: p.id }) }, '⚔ Attack…'),
        h('button.small.ghost', { type: 'button', onclick: () => attackDialog(null, { kind: 'player', id: p.id }) }, 'Attack them…')) : null,
      h('div.row.tight.between', h('span.hint', here ? 'On this map' : elsewhere ? `On ${elsewhere.name}` : 'Not placed'),
        h('span.row.tight',
          here ? h('button.small', { type: 'button', title: 'Take the token off this map', onclick: async () => { await api(`/api/players/${p.id}/unplace`, 'POST', {}); reloadContext(); } }, 'Unplace') : null,
          h('button.small' + (S.viewAs === p.id ? '.active' : ''), { type: 'button', title: 'See the map as this runner sees it (fog of war); click again for the GM view', onclick: () => { setMode('play'); setViewAs(S.viewAs === p.id ? "" : p.id); } }, S.viewAs === p.id ? 'Seeing as' : 'See as'),
          h('button.small', { type: 'button', onclick: () => { setMode('play'); setViewAs(p.id); setTool('token'); toast(`Click a room cell to place ${p.name}.`); } }, here ? 'Move' : 'Place')))));
  }
  if (!S.ctx.players.length && hasCampaign) el.innerHTML = '<p class="hint">No runners yet. Invite your players; once they join, place their tokens here.</p>';
}
$('btn-add-player').onclick = async () => { await SR.invite(S.ctx.campaign.id, S.ctx.campaign.name); };

// ------------------------------------------------------------ snapshots UI
function renderSnapshots() {
  const el = $('snapshot-list'); el.innerHTML = '';
  for (const s of S.ctx.snapshots) {
    const row = document.createElement('div'); row.className = 'mini-row';
    const sp = document.createElement('span'); sp.textContent = s.name; sp.title = new Date(s.createdAt * 1000).toLocaleString();
    const rs = document.createElement('button'); rs.textContent = 'Restore'; rs.className = 'small';
    rs.onclick = () => confirmDialog(`Restore "${s.name}"? Every runner's position, exploration and every door in this game goes back to that moment.`, async () => {
      await api(`/api/snapshots/${s.id}/restore`, 'POST', {}); await reloadContext(true); toast('Snapshot restored.');
    });
    const del = document.createElement('button'); del.textContent = '✕'; del.className = 'small danger'; del.title = 'Delete snapshot';
    del.onclick = () => confirmDialog(`Delete snapshot "${s.name}"?`, async () => { await api(`/api/snapshots/${s.id}`, 'DELETE'); S.ctx.snapshots = S.ctx.snapshots.filter(x => x !== s); renderSnapshots(); });
    row.append(sp, rs, del); el.appendChild(row);
  }
  if (!S.ctx.snapshots.length) el.innerHTML = '<p class="hint">No snapshots yet.</p>';
}
$('btn-snapshot').onclick = async () => {
  await flushFog(); if (S.dirty) await saveMap();
  const name = $('snapshot-name').value.trim() || new Date().toLocaleString();
  const r = await api(`/api/campaigns/${S.ctx.campaign.id}/snapshots`, 'POST', { name });
  S.ctx.snapshots.unshift({ id: r.id, name, createdAt: Date.now() / 1000 }); $('snapshot-name').value = ''; renderSnapshots(); toast('Snapshot saved.');
};

// ------------------------------------------------------------ inspector
function renderInspector() {
  const box = $('inspector');
  const emptyMsg = $('selected-empty');
  if (!S.selected) { box.hidden = true; if (emptyMsg) emptyMsg.hidden = false; $('tab-selected').classList.remove('has'); return; }
  const { c, r } = S.selected, cell = getCell(c, r), p = player();
  const wasHidden = box.hidden;
  box.hidden = false;
  if (emptyMsg) emptyMsg.hidden = true;
  $('tab-selected').classList.add('has');
  if (wasHidden && S.mode === 'play') Layout.show('selected');
  else if (wasHidden) requestAnimationFrame(() => box.scrollIntoView({ block: 'nearest', behavior: 'smooth' }));
  $('insp-title').textContent = `Cell ${c}, ${r}`;
  const close = document.createElement('button'); close.textContent = 'Close'; close.onclick = () => { S.selected = null; renderInspector(); requestDraw(); };
  $('insp-title').appendChild(close);
  const body = $('insp-body'); body.innerHTML = '';
  if (!cell) { body.innerHTML = '<p class="hint">Empty cell.</p>'; return; }
  const rm = roomOf(key(c, r));
  if (rm) { const d = document.createElement('p'); d.className = 'hint'; d.textContent = 'Room: ' + rm.name; body.appendChild(d); }
  const flags = document.createElement('div');
  if (S.mode === 'edit') {
    flags.innerHTML = `<label class="check"><input type="checkbox" id="insp-secret" ${cell.secret ? 'checked' : ''}> Secret</label>`;
    flags.querySelector('#insp-secret').onchange = e => { cell.secret = e.target.checked; markDirty(); renderLegend(); };
  } else if (p) {
    const k = key(c, r);
    flags.innerHTML = `<label class="check"><input type="checkbox" id="insp-explored" ${pms(p).explored[k] ? 'checked' : ''}> Explored by ${escapeHtml(p.name)}</label>`;
    flags.querySelector('#insp-explored').onchange = e => fogAction([p.id], [k], e.target.checked ? 'reveal' : 'hide');
  }
  body.appendChild(flags);
  const g = G(), names = g.edgeNames;
  for (let e = 0; e < g.edgeCount; e++) {
    const d = doorOnEdge(g, cells(), c, r, e); if (!d) continue;
    const own = !!((cell.doors || {})[e]);
    const row = document.createElement('div'); row.className = 'insp-door';
    const lbl = document.createElement('span'); const dot = document.createElement('span'); dot.className = 'dot'; dot.style.background = d.color; lbl.append(dot, `${names[e]} door`);
    const btns = document.createElement('span');
    const tg = document.createElement('button'); tg.textContent = d.open ? 'Close' : 'Open'; tg.disabled = !!d.locked;
    tg.onclick = () => toggleDoorAt(c, r, e, false);
    const lk = document.createElement('button'); lk.textContent = d.locked ? 'Unlock' : 'Lock'; lk.title = 'Locked doors cannot be opened by players';
    lk.onclick = () => toggleDoorAt(c, r, e, true);
    btns.append(tg, lk);
    if (d.locked) lbl.append(' (locked)');
    if (S.mode === 'edit' && own) { const rmv = document.createElement('button'); rmv.textContent = 'Remove'; rmv.className = 'danger'; rmv.onclick = () => { delete cell.doors[e]; if (!Object.keys(cell.doors).length) delete cell.doors; markDirty(); renderInspector(); renderLegend(); }; btns.appendChild(rmv); }
    row.append(lbl, btns); body.appendChild(row);
  }
  const m = markerAt(c, r);
  if (m) {
    const row = document.createElement('div'); row.className = 'insp-marker';
    const t = MARKER_BY_ID[m.type] || MARKER_TYPES[0];
    const sp = document.createElement('span'); sp.textContent = t.name; row.appendChild(sp);
    if (m.linkId) { const tm = m.target && S.ctx.allMaps.find(x => x.id === m.target.mapId); const s2 = document.createElement('span'); s2.className = 'hint'; s2.textContent = `→ ${tm ? tm.name + ` (${m.target.c}, ${m.target.r})` : 'resolved by ID'} · ID ${m.linkId}`; row.appendChild(s2);
      const unl = document.createElement('button'); unl.textContent = 'Remove link'; unl.className = 'small'; unl.onclick = () => { pushUndo(); delete m.linkId; delete m.target; markDirty(); renderInspector(); }; if (S.mode === 'edit') row.appendChild(unl); }
    const hid = document.createElement('label'); hid.className = 'check'; const hidCb = document.createElement('input'); hidCb.type = 'checkbox'; hidCb.checked = !!m.hidden;
    hidCb.onchange = () => { if (S.mode === 'edit') { if (hidCb.checked) m.hidden = true; else delete m.hidden; markDirty(); } else updateMarkerLive(m, { hidden: hidCb.checked }); if (!hidCb.checked) delete m.hidden; invalidate(); renderLegend(); };
    hid.append(hidCb, ' Hidden from players'); row.appendChild(hid);
    const inp = document.createElement('input'); inp.value = m.label || ''; inp.placeholder = 'label'; inp.className = 'grow';
    inp.onchange = () => updateMarkerLive(m, { label: inp.value.trim() });
    row.appendChild(inp);
    const info = h('textarea.marker-info', { rows: 2, maxlength: 600, placeholder: 'What players see when they right-click it (optional)', value: m.info || '' });
    info.onchange = () => { const v = info.value.trim(); updateMarkerLive(m, { info: v }); if (!v) delete m.info; };
    row.appendChild(info);
    row.appendChild(markerNpc(m));
    row.appendChild(markerCM(m));
    row.appendChild(statusEditor(m.statuses || {}, (name, on, value) => {
      if (S.mode === 'edit') { const st = Object.assign({}, m.statuses || {}); if (on) st[name] = value; else delete st[name]; updateMarkerLive(m, { statuses: Object.keys(st).length ? st : null }); renderInspector(); return; }
      setStatus({ kind: 'marker', id: m.id }, name, on, value).then(r => { if (r) { m.statuses = r; if (!Object.keys(r).length) delete m.statuses; invalidate(); renderInspector(); } });
    }));
    if (S.mode === 'play' && S.ctx.campaign) row.appendChild(h('div.row.tight', h('button.small', { type: 'button', onclick: () => attackDialog({ kind: 'marker', id: m.id }) }, '⚔ Attack…'),
      h('button.small.ghost', { type: 'button', onclick: () => attackDialog(null, { kind: 'marker', id: m.id }) }, 'Attack it…'),
      S.tracker && S.tracker.active && !S.tracker.entries.some(e => e.ref === m.id) ? h('button.small.ghost', { type: 'button', onclick: () => trackerOp('add', { mapId: MAP_ID, markers: [m.id], roll: true }) }, '+ Initiative') : null));
    if (S.mode === 'edit') {
      const rmv = document.createElement('button'); rmv.textContent = 'Remove'; rmv.className = 'danger';
      rmv.onclick = () => { pushUndo(); S.map.data.markers = markers().filter(x => x !== m); markDirty(); renderInspector(); renderLegend(); };
      row.appendChild(rmv);
    }
    body.appendChild(row);
  }
}

function markerCM(m) {
  const box = h('div.cm-edit');
  if (m.cm) {
    const dmg = (track, n) => {
      if (S.mode === 'edit') {
        pushUndo(); S.rt.markers.add(m.id);
        if (m.cm.grunt) { m.cm.p = Math.max(0, Math.min(m.cm.pm, m.cm.p + n)); if (n > 0) m.cm.last = track === 'stun' ? 'S' : 'P'; }
        else { const k = track === 'stun' ? 's' : 'p'; m.cm[k] = Math.max(0, m.cm[k] + n); if (k === 's' && m.cm.s > m.cm.sm) { m.cm.p += m.cm.s - m.cm.sm; m.cm.s = m.cm.sm; } }
        markDirty(); renderInspector(); return;
      }
      api(`/api/maps/${MAP_ID}/marker`, 'POST', { id: m.id, damage: { track, amount: n } }).then(r => { m.cm = r.marker.cm; invalidate(); renderInspector(); }).catch(e => toast(e.message));
    };
    const set = (track, value) => dmg(track, value - (track === 'stun' && !m.cm.grunt ? m.cm.s : m.cm.p));
    if (m.cm.grunt) box.append(SR.monitor('physical', m.cm, { onSet: set, compact: true, showTools: false }), h('div.row.tight', h('button.small', { type: 'button', onclick: () => dmg('physical', 1) }, '+1 P'),
      h('button.small', { type: 'button', onclick: () => dmg('stun', 1) }, '+1 S'), h('button.small', { type: 'button', onclick: () => dmg('physical', -1) }, 'Heal'),
      m.npc && m.npc.pr != null && m.cm.p > m.npc.pr ? h('span.warn', { title: 'Damage exceeds their Professional Rating: Composure test or they bail' }, 'May flee') : null));
    else if (m.cm.pm) box.append(SR.monitor('physical', m.cm, { onSet: set, compact: true, showTools: false }), h('div.row.tight', h('button.small', { type: 'button', onclick: () => dmg('physical', 1) }, '+1 P'), h('button.small', { type: 'button', onclick: () => dmg('physical', -1) }, 'Heal P')));
    if (m.cm.sm) box.append(SR.monitor('stun', m.cm, { onSet: set, compact: true, showTools: false }), h('div.row.tight', h('button.small', { type: 'button', onclick: () => dmg('stun', 1) }, '+1 S'), h('button.small', { type: 'button', onclick: () => dmg('stun', -1) }, 'Heal S')));
    const st = GridCore.cmStatus(m.cm);
    box.append(h('div.row.tight', SR.healthTag(st), h('button.small.ghost', { type: 'button', onclick: () => updateMarkerLive(m, { cm: null }).then(() => { delete m.cm; invalidate(); renderInspector(); }) }, 'Remove monitor')));
  } else {
    const b = h('input', { type: 'number', min: 1, max: 20, placeholder: 'Body' }), w = h('input', { type: 'number', min: 1, max: 20, placeholder: 'Wil' });
    box.append(h('div.row.tight', h('span.hint', 'Monitor:'), b, w, h('button.small', { type: 'button', onclick: () => { const cm = cmFromAttrs(+b.value, +w.value); if (!cm) { toast('Enter Body and/or Willpower.'); return; } updateMarkerLive(m, { cm }); renderInspector(); } }, 'Add')));
  }
  return box;
}

/* NPC stat block on a marker (core-book templates) */
function markerNpc(m) {
  const box = h('div.npc-box');
  const pick = h('button.small', { type: 'button', onclick: () => pickTemplate(m) }, m.npc ? 'Change template…' : 'Apply NPC template…');
  if (!m.npc) { box.append(h('div.row.tight', pick)); return box; }
  const n = m.npc, A = n.attrs || {};
  box.append(h('div.row.between', h('b', n.template || 'NPC'), pick),
    h('div.hint', Object.entries(A).filter(([, v]) => v).map(([k, v]) => `${k.slice(0, 3).toUpperCase()} ${v}`).join(' · ')),
    h('div.hint', `DR ${n.dr} · Init ${n.init} + ${n.init_dice}D6 · ${n.grunt ? `Grunt, PR ${n.pr} (group Edge ${n.edge})` : n.kind}` + (n.move ? ` · Move ${n.move}` : '')),
    n.weapons.length ? h('div.hint', 'Weapons: ' + n.weapons.map(w => `${w.name} ${w.dv}${w.type}${w.grenade ? '' : ' AR ' + SR.arText(w.ar)}`).join('; ')) : null,
    h('details', h('summary.hint', 'Skills & notes'), h('div.hint', Object.entries(n.skills || {}).map(([k, v]) => `${k} ${v}`).join(', ')), h('pre.hint', { style: { whiteSpace: 'pre-wrap' } }, n.notes || '')));
  if (n.kind === 'Vehicle' || n.kind === 'Drone') box.append(vehicleBox(m));
  return box;
}
/* A vehicle or drone marker: speed (Speed Interval penalties, ramming DV) and weapon mounts */
function vehicleBox(m) {
  const n = m.npc, v = n.vehicle || {}, linked = !!n.link;
  const accel = +v.accel || 0, interval = +v.speed_interval || 0, speed = +v.speed || 0;
  const send = async body => {
    try { const r = await api(`/api/maps/${MAP_ID}/marker`, 'POST', { id: m.id, ...body }); Object.assign(m, r.marker); invalidate(); renderInspector(); if (linked) reloadContext(); }
    catch (e) { toast(e.message); }
  };
  const box = h('div.vehicle-box');
  const pen = interval ? Math.floor(speed / interval) : 0;
  box.append(h('div.row.tight', h('b', 'Speed'),
    linked ? h('span.hint', 'kept on the owner’s sheet') : h('span', `${speed} m/round`, pen ? h('span.warn', ` · −${pen} dice, +${pen} ram DV`) : null),
    h('button.small', { type: 'button', title: `Slow down by up to ${accel} m (Acceleration)`, onclick: () => send({ vehicleSpeed: { change: -accel } }) }, `−${accel}`),
    h('button.small', { type: 'button', title: `Speed up by up to ${accel} m (Acceleration)`, onclick: () => send({ vehicleSpeed: { change: accel } }) }, `+${accel}`),
    h('button.small.ghost', { type: 'button', onclick: () => send({ vehicleSpeed: { set: 0 } }) }, 'Stop')),
    h('div.hint', `Speed Interval ${interval || '—'}, top speed ${v.top_speed || '—'}: −1 die per interval on Handling tests and attacks from it.`));
  if (linked) { box.append(h('div.hint', 'Its weapon mounts are on the owner’s sheet; the drone fires them from the attack dialog.')); return box; }
  const room = Math.floor((+v.body || 0) / SR.CAT.combat.mounts.bodyPerMount);
  const mounted = (n.weapons || []).map((w, i) => [w, i]).filter(([w]) => w.mount);
  const used = mounted.reduce((a, [w]) => a + (w.mount === 'heavy' ? 2 : 1), 0);
  box.append(h('div.row.tight.mt', h('b', 'Weapon mounts'), h('span.hint', `${used} of ${room} used (Body / 3; heavy counts 2)`),
    used < room ? h('button.small', { type: 'button', onclick: () => mountDialog(m, send, room - used) }, 'Mount a weapon…') : null));
  for (const [w, i] of mounted) box.append(h('div.row.tight', h('span.grow', `${w.name} (${w.mount}) · ${w.pool} dice: ${w.pool_label}`),
    h('button.small.ghost', { type: 'button', title: 'Remove it', onclick: () => send({ unmount: i }) }, '✕')));
  return box;
}
async function mountDialog(m, send, free) {
  const M = SR.CAT.combat.mounts, ok_ = new Set(free >= 2 ? [...M.standard, ...M.heavy] : M.standard);
  const items = SR.CAT.store.items.filter(e => e.cat === 'Ranged' && ok_.has(e.sub)).sort((a, b) => a.name.localeCompare(b.name));
  const sel = h('select', items.map(e => option(e.id, `${e.name} (${e.sub}${M.heavy.includes(e.sub) ? ', heavy mount' : ''}) · DV ${e.dv}`)));
  const rating = h('input', { type: 'number', min: 0, max: 9, value: 3, style: { width: '4.5rem' } });
  const ok = await UI.modal('Mount a weapon', h('div', h('p.hint', 'The drone fires it with Sensor + its Targeting autosoft (Sensor − 1 without one). Standard mounts take an assault rifle or smaller; machine guns, sniper rifles and launchers need a heavy mount (two of the vehicle’s mounts).'),
    h('label.stack', 'Weapon', sel), h('label', 'Targeting autosoft rating (0 = none)', rating)), { ok: 'Mount', narrow: true });
  if (ok) send({ mount: { ref: sel.value, autosoft: +rating.value || 0 } });
}
async function pickTemplate(m) {
  const sel = h('select', option('', 'Pick a template…'));
  templateGroups(sel);
  const force = h('input', { type: 'number', min: 1, max: 12, value: 3 }), relabel = h('input', { type: 'checkbox', checked: !m.label });
  const ok = await UI.modal('NPC template', h('div', h('p.hint', 'Sets this marker’s stats, weapons and condition monitor (damage is reset).'), h('label.stack', 'Template', sel),
    h('label.stack', 'Force (spirits) or host rating (IC)', force), h('label.check', relabel, 'Rename the marker after the template')), { ok: 'Apply', narrow: true });
  if (!ok || !sel.value) return;
  if (S.mode === 'edit') {
    try { const t = await api(`/api/npc-templates/${encodeURIComponent(sel.value)}?force=${+force.value || 3}`); pushUndo(); m.npc = t.npc; m.cm = t.cm; if (relabel.checked) m.label = t.npc.template; S.rt.markers.add(m.id); markDirty(); renderInspector(); }
    catch (e) { toast(e.message); }
    return;
  }
  try { const r = await api(`/api/maps/${MAP_ID}/marker`, 'POST', { id: m.id, template: sel.value, force: +force.value || 3, relabel: relabel.checked }); Object.assign(m, r.marker); invalidate(); renderInspector(); }
  catch (e) { toast(e.message); }
}
/* status checkboxes: chips you can remove plus a picker to add one */
function statusEditor(statuses, onChange) {
  const sel = h('select.small', option('', '+ status…'), Object.entries(SR.CAT.statuses).map(([k, v]) => option(k, `${v.icon} ${k}`)));
  sel.onchange = async () => {
    const name = sel.value; sel.value = ''; if (!name) return;
    const meta = SR.CAT.statuses[name]; let value = true;
    if (meta.value || meta.levels) { const v = await UI.prompt(name, meta.levels ? `Level (1-${meta.levels})` : 'Value (#)', { type: 'number', value: 1, min: 1 }); if (v === null) return; value = Math.max(1, +v || 1); }
    onChange(name, true, value);
  };
  return h('div.status-edit', SR.statusChips(statuses, { onRemove: n => onChange(n, false) }), sel);
}
async function setStatus(target, status, on, value) {
  try { const r = await api(`/api/maps/${MAP_ID}/status`, 'POST', { target, status, on, value: value === true ? 1 : value }); if (target.kind === 'player') reloadContext(); return r.statuses; }
  catch (e) { toast(e.message); return null; }
}

// ------------------------------------------------------------ combat: initiative tracker
async function trackerOp(op, body = {}) {
  if (!S.ctx.campaign) return;
  try { const r = await api(`/api/games/${S.ctx.campaign.id}/combat`, 'POST', { op, ...body }); S.tracker = r.tracker; renderCombat(); if (r.message) toast(r.message); }
  catch (e) { toast(e.message); }
}
function combatants() {
  const out = [];
  for (const p of S.ctx.players) { const t = p.currentMapId === MAP_ID && (p.state.maps || {})[MAP_ID]?.token; if (t) out.push({ kind: 'player', id: p.id, name: p.name, c: t.c, r: t.r, color: p.color }); }
  for (const m of markers()) if (m.npc || m.cm) out.push({ kind: 'marker', id: m.id, name: m.label || (m.npc && m.npc.template) || (MARKER_BY_ID[m.type] || MARKER_TYPES[0]).name, c: m.c, r: m.r, color: m.color, hidden: m.hidden });
  return out;
}
function renderCombat() {
  const root = $('combat-root'); if (!root) return;
  root.innerHTML = '';
  const strip = $('combat-panel');
  strip.hidden = !S.ctx.campaign || S.mode !== 'play';
  const t = S.tracker;
  strip.classList.toggle('active', !!(t && t.active));
  if (!t || !t.active) {
    root.append(h('span.strip-idle', 'No combat running.'),
      h('button.small.primary', { type: 'button', onclick: startCombat }, 'Start combat…'),
      h('button.small', { type: 'button', onclick: () => attackDialog() }, '⚔ Attack…'));
    Layout.relayout();
    return;
  }
  const order = h('div.strip-order', { role: 'list' });
  for (const e of t.entries) {
    const chip = h('button.strip-chip' + (e.current ? '.current' : '') + (e.hidden ? '.hidden-npc' : '') + (e.total == null ? '.unrolled' : ''),
      { type: 'button', role: 'listitem', title: `${e.name}: ${e.total == null ? 'no initiative yet' : 'initiative ' + e.total}${e.minor ? ` · 1 Major + ${e.minor} Minor` : ''}${e.hidden ? ' · hidden from players' : ''}. Click for options.`,
        onclick: ev => chipMenu(e, ev.currentTarget) },
      h('span.dot', { style: { background: e.color } }), h('span.nm', e.name),
      h('b.sc', e.total == null ? '–' : e.total), SR.actionPips(e), e.hidden ? h('span.eye', { title: 'Hidden from players' }, '◌') : null,
      e.surprised ? h('span.flag', { title: 'Surprised: no actions or Edge this round' }, '!') : null,
      e.cs && e.cs.until >= t.round ? h('span.flag.cs', { title: `Counterspell by ${e.cs.by}: +${e.cs.hits} vs spells until round ${e.cs.until}` }, '✦') : null,
      e.aim ? h('span.flag', { title: `Taking aim: +${e.aim} on the next ranged attack` }, `🎯${e.aim}`) : null,
      e.grapple ? h('span.flag', { title: e.grapple.role === 'held' ? 'Restrained in a grapple' : 'Holding someone in a grapple' }, e.grapple.role === 'held' ? '🤼' : '✊') : null);
    order.append(chip);
  }
  if (!t.entries.length) order.append(h('span.strip-idle', 'Nobody in the order yet. Use + Add.'));
  const cur = t.entries.find(x => x.current);
  const ongoing = combatants().some(c => { const st = c.kind === 'player' ? ((S.ctx.players.find(p => p.id === c.id) || {}).statuses || {}) : ((markers().find(m => m.id === c.id) || {}).statuses || {}); return (SR.CAT.combat.ongoing || []).some(k => st[k]); });
  const controls = h('div.strip-controls',
    ongoing ? h('button.small.warn', { type: 'button', title: 'Everyone Burning, Corrosive or Poisoned resists the damage now (start of a round)', onclick: () => trackerOp('ongoing') }, '🔥 Ongoing damage') : null,
    h('label.check', { title: 'Players see the order (hidden enemies stay hidden)' }, h('input', { type: 'checkbox', checked: t.visible, onchange: e => trackerOp(e.target.checked ? 'show' : 'hide') }), 'Players see it'),
    h('button.small', { type: 'button', title: 'Roll initiative for every NPC', onclick: () => trackerOp('roll') }, 'Roll NPCs'),
    h('button.small', { type: 'button', onclick: addToCombat }, '+ Add'),
    h('button.small', { type: 'button', title: 'Initiative isn’t rerolled in SR6: back to the top of the order', onclick: () => trackerOp('round') }, 'New round'),
    h('button.small', { type: 'button', title: 'Attack with whoever’s turn it is', onclick: () => attackDialog(cur && cur.kind !== 'custom' ? { kind: cur.kind, id: cur.ref } : undefined) }, '⚔ Attack…'),
    h('button.small.primary', { type: 'button', onclick: () => trackerOp('next') }, 'Next turn ›'),
    h('button.small.ghost.danger', { type: 'button', title: 'End combat', onclick: async () => { if (await UI.confirm('End combat? The initiative order is cleared.', { ok: 'End combat', danger: true })) trackerOp('end'); } }, 'End'));
  root.append(h('span.strip-round', `Round ${t.round}`), order, controls);
  const curEl = order.querySelector('.current');
  if (curEl) curEl.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  Layout.relayout();
}
/* options for one combatant, opened from its chip in the strip */
function chipMenu(e, anchor) {
  document.querySelectorAll('.chip-menu').forEach(x => x.remove());
  const score = h('input', { type: 'number', value: e.total ?? '', placeholder: '–', style: { width: '4.5rem' }, onchange: ev => trackerOp('set', { id: e.id, total: ev.target.value }) });
  const close = () => { menu.remove(); document.removeEventListener('pointerdown', outside, true); };
  const act = fn => () => { close(); fn(); };
  const menu = h('div.chip-menu', { role: 'menu' },
    h('div.cm-head', h('span.dot', { style: { background: e.color } }), h('b', e.name), e.minor ? h('span.hint', `1 Major + ${e.minor} Minor`) : null),
    h('div.cm-actions', h('span', 'Actions left ', SR.actionPips(e)),
      h('span.row.tight', h('button.small', { type: 'button', title: 'Spend a Major Action', onclick: act(() => trackerOp('use', { id: e.id, action: 'major', delta: 1 })) }, 'Use Major'),
        h('button.small', { type: 'button', title: 'Spend a Minor Action', onclick: act(() => trackerOp('use', { id: e.id, action: 'minor', delta: 1 })) }, 'Use Minor'),
        h('button.small.ghost', { type: 'button', title: 'Give back all actions for this round', onclick: act(() => trackerOp('use', { id: e.id, reset: true, delta: 0 })) }, 'Reset'))),
    h('label', 'Initiative', score),
    h('button', { type: 'button', onclick: act(() => { trackerOp('turn', { id: e.id }); focusCombatant(e); }) }, 'Make it their turn'),
    h('button', { type: 'button', onclick: act(() => focusCombatant(e)) }, 'Show on the map'),
    h('button', { type: 'button', onclick: act(() => trackerOp('roll', { id: e.id })) }, 'Roll initiative'),
    e.kind !== 'custom' ? h('button', { type: 'button', onclick: act(() => attackDialog({ kind: e.kind, id: e.ref })) }, '⚔ Attack with them…') : null,
    e.kind !== 'custom' ? h('button', { type: 'button', onclick: act(() => attackDialog(null, { kind: e.kind, id: e.ref })) }, 'Attack them…') : null,
    e.kind !== 'custom' ? h('button', { type: 'button', title: SR.CAT.combat.takeAim.desc, disabled: e.aimRound === (S.tracker || {}).round,
      onclick: act(() => trackerOp('aim', { id: e.id })) }, `🎯 Take Aim${e.aim ? ` (+${e.aim} now)` : ''}`) : null,
    e.kind !== 'custom' ? h('button', { type: 'button', title: SR.CAT.combat.counterspell.desc, onclick: act(() => counterspellDialog(e)) }, '✦ Counterspell…') : null,
    e.kind !== 'custom' ? h('button', { type: 'button', title: SR.CAT.combat.dispel.desc, onclick: act(() => dispelDialog(e)) }, '✦ Dispel a spell…') : null,
    e.grapple ? h('div.cm-grapple', h('span.hint', e.grapple.role === 'held' ? 'Restrained:' : 'Grappling:'),
      Object.entries(SR.CAT.combat.grapple).filter(([, g]) => g.held === (e.grapple.role === 'held')).map(([k, g]) =>
        h('button.small', { type: 'button', title: g.desc, onclick: act(async () => { await trackerOp('grapple', { id: e.id, action: k }); await reloadContext(); }) }, g.name))) : null,
    e.kind !== 'player' ? h('button', { type: 'button', onclick: act(() => trackerOp('set', { id: e.id, hidden: !e.hidden })) }, e.hidden ? 'Reveal to players' : 'Hide from players') : null,
    h('button.danger', { type: 'button', onclick: act(() => trackerOp('remove', { id: e.id })) }, 'Remove from combat'));
  document.body.append(menu);
  const r = anchor.getBoundingClientRect();
  menu.style.left = Math.min(window.innerWidth - menu.offsetWidth - 8, Math.max(8, r.left)) + 'px';
  menu.style.top = (r.bottom + 6) + 'px';
  const outside = ev => { if (!menu.contains(ev.target)) close(); };
  setTimeout(() => document.addEventListener('pointerdown', outside, true), 0);
  score.focus();
}
function focusCombatant(e) {
  const c = combatants().find(x => x.kind === e.kind && x.id === e.ref);
  if (c) { const p = G().cellCenter(c.c, c.r); vp.centerOn(p.x, p.y); S.selected = { c: c.c, r: c.r }; renderInspector(); requestDraw(); }
}
function combatantPicker(list, checkedFn) {
  return h('div.check-grid', list.map(c => h('label.check', h('input', { type: 'checkbox', checked: checkedFn(c), dataset: { kind: c.kind, id: c.id } }), h('span.dot', { style: { background: c.color } }), c.name + (c.hidden ? ' (hidden)' : ''))));
}
async function startCombat() {
  const list = combatants();
  const picker = combatantPicker(list, () => true);
  const roll = h('input', { type: 'checkbox', checked: true }), vis = h('input', { type: 'checkbox' }), surp = h('input', { type: 'checkbox' });
  const amb = combatantPicker(list, () => false);
  const ambBox = h('div.mt', { hidden: true }, h('p.hint', 'Who set up the ambush? They don’t roll.'), amb);
  surp.onchange = () => { ambBox.hidden = !surp.checked; };
  const ok = await UI.modal('Start combat', h('div', list.length ? picker : h('p.hint', 'No tokens or enemy markers on this map. You can still add combatants later.'),
    h('label.check.mt', roll, 'Roll initiative for the NPCs now'), h('label.check', vis, 'Show the order to players right away'),
    h('label.check', { title: 'Reaction + Intuition (3): whoever fails can’t act or spend Edge in the first round' }, surp, 'Surprise test for everyone but the ambushers'), ambBox,
    h('p.hint', 'Players roll their own initiative from their dice panel; it lands here.')), { ok: 'Start' });
  if (!ok) return;
  const sel = [...picker.querySelectorAll('input:checked')].map(i => i.dataset);
  const ambushers = [...amb.querySelectorAll('input:checked')].map(i => i.dataset.id);
  await trackerOp('start', { players: sel.filter(x => x.kind === 'player').map(x => x.id), mapId: MAP_ID, markers: sel.filter(x => x.kind === 'marker').map(x => x.id),
    roll: roll.checked, visible: vis.checked, surprise: surp.checked, ambushers });
}
/* Counterspelling (boosted defense): a Major Action; Sorcery + Magic hits protect the chosen combatants against spells */
async function counterspellDialog(e) {
  const others = (S.tracker.entries || []);
  const picker = h('div.check-grid', others.map(x => h('label.check', h('input', { type: 'checkbox', checked: x.id === e.id || x.kind === e.kind, dataset: { id: x.id } }),
    h('span.dot', { style: { background: x.color } }), x.name)));
  const force = h('input', { type: 'checkbox' });
  const ok = await UI.modal(`${e.name}: counterspell`, h('div', h('p.hint', SR.CAT.combat.counterspell.desc + ' Everyone within a 2 m radius (more with reagents) can be protected.'),
    picker, h('label.check.mt', force, 'Ignore action limits')), { ok: 'Roll Sorcery + Magic' });
  if (!ok) return;
  await trackerOp('counterspell', { id: e.id, protect: [...picker.querySelectorAll('input:checked')].map(i => i.dataset.id), force: force.checked });
}
/* Dispelling: a Counterspell Major Action against a sustained spell, a runner's or one the GM describes */
async function dispelDialog(e) {
  let spells = [];
  try { spells = (await api(`/api/games/${S.ctx.campaign.id}/sustained`)).spells; } catch (err) { toast(err.message); }
  const name = h('input', { placeholder: 'e.g. Mana Barrier on the guards' }), dv = h('input', { type: 'number', min: 1, max: 30, value: 4, style: { width: '4.5rem' } }),
    hits = h('input', { type: 'number', min: 0, max: 30, value: 2, style: { width: '4.5rem' } });
  const radios = spells.map((s, i) => h('label.check', h('input', { type: 'radio', name: 'dispel-target', value: String(i), checked: i === 0 }),
    `${s.name} (${s.who}): ${s.hits} hit${s.hits === 1 ? '' : 's'}, Drain Value ${s.dv}`));
  const other = h('label.check', h('input', { type: 'radio', name: 'dispel-target', value: 'other', checked: !spells.length }), 'Another spell:');
  const force = h('input', { type: 'checkbox' });
  const ok = await UI.modal(`${e.name}: dispel`, h('div', h('p.hint', SR.CAT.combat.dispel.desc),
    radios.length ? h('div.col', radios) : h('p.hint', 'No runner is sustaining a spell.'),
    h('div.row.tight.mt', other, name, h('label', 'Drain Value', dv), h('label', 'Its hits', hits)),
    h('label.check.mt', force, 'Ignore action limits')), { ok: 'Roll Sorcery + Magic' });
  if (!ok) return;
  const pick = (document.querySelector('input[name=dispel-target]:checked') || {}).value;
  const target = pick === 'other' || pick == null ? { name: name.value.trim() || 'the spell', dv: +dv.value || 3, hits: +hits.value || 0 }
    : { pid: spells[+pick].pid, index: spells[+pick].index };
  await trackerOp('dispel', { id: e.id, target, force: force.checked });
  await reloadContext();
}
async function addToCombat() {
  const inT = new Set((S.tracker.entries || []).map(e => e.ref));
  const list = combatants().filter(c => !inT.has(c.id));
  const picker = combatantPicker(list, () => false);
  const name = h('input', { placeholder: 'or a custom combatant…' }), score = h('input', { type: 'number', min: 0, value: 8, style: { width: '4rem' } }), dice = h('input', { type: 'number', min: 1, max: 5, value: 1, style: { width: '3.5rem' } });
  const ok = await UI.modal('Add to combat', h('div', list.length ? picker : h('p.hint', 'Everyone on this map is already in.'),
    h('div.row.tight.mt', name, h('label', 'Init', score), h('label', 'D6', dice))), { ok: 'Add' });
  if (!ok) return;
  const sel = [...picker.querySelectorAll('input:checked')].map(i => i.dataset);
  await trackerOp('add', { players: sel.filter(x => x.kind === 'player').map(x => x.id), mapId: MAP_ID, markers: sel.filter(x => x.kind === 'marker').map(x => x.id), roll: true,
    custom: name.value.trim() ? { name: name.value.trim(), score: +score.value, dice: +dice.value } : null });
}

// ------------------------------------------------------------ combat: GM-resolved attack
function cellDistance(a, b) {
  const g = G();
  if (!g.hex) return Math.max(Math.abs(a.c - b.c), Math.abs(a.r - b.r));
  const cube = p => { const x = p.c, z = p.r - (p.c - (p.c & 1)) / 2; return [x, -x - z, z]; };
  const [x1, y1, z1] = cube(a), [x2, y2, z2] = cube(b);
  return Math.max(Math.abs(x1 - x2), Math.abs(y1 - y2), Math.abs(z1 - z2));
}
function bandFor(m) { return m <= 3 ? 'Close' : m <= 50 ? 'Near' : m <= 250 ? 'Medium' : m <= 500 ? 'Far' : 'Extreme'; }
async function attackDialog(attacker, target) {
  if (!S.ctx.campaign) { toast('Assign this map to a game first.'); return; }
  const list = combatants();
  if (list.length < 2) { toast('You need at least two combatants on this map (runner tokens or markers with a monitor).'); return; }
  const RULES = SR.CAT.combat;
  const optKey = c => `${c.kind}:${c.id}`;
  const refOf = k => { const [kind, id] = k.split(':'); return { kind, id }; };
  const pos = v => list.find(c => optKey(c) === v);
  const dead = c => c.kind === 'marker' && GridCore.cmStatus((markers().find(m => m.id === c.id) || {}).cm) === 'Dead';
  const attSel = h('select', list.map(c => option(optKey(c), c.name, attacker && attacker.kind === c.kind && attacker.id === c.id)));
  let firstTarget = target ? `${target.kind}:${target.id}` : null;
  if (!firstTarget) {
    const ak = attSel.value.split(':')[0];
    const other = list.find(c => c.kind !== ak && !dead(c)) || list.find(c => optKey(c) !== attSel.value);
    firstTarget = other ? optKey(other) : null;
  }
  const targets = [];                    // [{key, info, sight, defense, cover}]
  const weapon = h('select'), mode = h('select'), range = h('select', SR.RANGES.map(r => option(r, `${r} (${SR.CAT.store.rangeMeters[r]})`)));
  const info = h('p.attack-info'), distInfo = h('span.hint'), attInfo = h('p.hint');
  let cellM = 2; try { cellM = +localStorage.getItem('sg.cellMeters') || 2; } catch { /* ignore */ }
  const meters = h('input', { type: 'number', min: 0.5, step: 0.5, value: cellM, style: { width: '4rem' }, title: 'Meters per cell', onchange: () => { try { localStorage.setItem('sg.cellMeters', meters.value); } catch { /* ignore */ } suggestRange(); } });
  const amod = h('input', { type: 'number', value: 0 }), dmod = h('input', { type: 'number', value: 0 }), smod = h('input', { type: 'number', value: 0 });
  const amp = h('input', { type: 'number', min: 0, max: 10, value: 0 }), xdv = h('input', { type: 'number', value: 0 }), dice = h('input', { type: 'number', min: 0, placeholder: 'auto' });
  const chk = (on, title) => h('input', { type: 'checkbox', checked: !!on, title });
  const wild = chk(), hidden = chk(), unopp = chk(), apply = chk(true), autoEdge = chk(true), ignoreSight = chk(), ignoreActions = chk(), intercept = chk(), anticip = chk();
  const aimNow = chk(false, RULES.takeAim.desc), trip = chk(false, RULES.trip.desc), grapple = chk(false, 'Unarmed: on a hit, Strength + net hits vs their Strength to hold them (no damage)');
  const aimInfo = h('span.hint');
  const called = h('select', option('', 'No called shot'), Object.entries(RULES.calledShots).map(([k, v]) => option(k, `${v.name}${v.edge ? ` · ${v.edge} Edge` : ''}`)));
  const eaSel = h('select', option('', 'No Edge action'), Object.entries(RULES.edgeActions || {}).map(([k, v]) => h('option', { value: k, title: v.desc }, `${v.name} · ${v.edge} Edge`)));
  const astType = h('select', { title: 'In astral combat the attacker chooses' }, option('S', 'Stun'), option('P', 'Physical'));
  const astLabel = h('label', { hidden: true }, 'Astral damage', astType);
  const tgtBox = h('div.attack-targets');
  const addSel = h('select', { 'aria-label': 'Add a target' });
  let options = [], attOpts = {};

  const cur = () => options.find(x => x.key === weapon.value) || {};
  function suggestRange() {
    const a = pos(attSel.value), b = targets[0] && pos(targets[0].key); if (!a || !b) return;
    const d = cellDistance(a, b), m = d * (+meters.value || 2);
    distInfo.textContent = `${d} cells ≈ ${m} m`;
    range.value = bandFor(m); describe();
  }
  async function loadAttacker() {
    const [kind, id] = attSel.value.split(':');
    try { attOpts = await api(`/api/maps/${MAP_ID}/attack-options`, 'POST', { who: { kind, id } }); options = attOpts.options; }
    catch (e) { toast(e.message); options = []; attOpts = {}; }
    weapon.innerHTML = '';
    options.forEach(o => weapon.append(option(o.key, `${o.name} · ${o.pool} dice · DV ${o.dv}`)));
    picked = false;
    for (const t of targets) await loadTarget(t);
    drawModes(); suggestRange(); pickReachable(); drawTargets();
  }
  let picked = false;
  function pickReachable() {
    if (picked) return;
    const i = SR.RANGES.indexOf(range.value);
    const o = cur();
    if (o.ar && (o.ar[i] != null || o.astral)) return;
    const ok = options.find(x => x.ar && x.ar[i] != null);
    if (ok) { weapon.value = ok.key; drawModes(); }
  }
  async function loadTarget(t) {
    const ref = refOf(t.key);
    try { t.info = await api(`/api/maps/${MAP_ID}/attack-options`, 'POST', { who: ref }); } catch { t.info = { dr: 0, defense: {} }; }
    try { t.sight = (await api(`/api/maps/${MAP_ID}/sight`, 'POST', { a: refOf(attSel.value), b: ref })).sight; } catch { t.sight = null; }
  }
  async function addTarget(key) {
    if (!key || key === attSel.value || targets.some(t => t.key === key)) return;
    const t = { key, defense: '', cover: 'auto' };
    targets.push(t);
    await loadTarget(t);
    if (targets.length === 1) suggestRange();
    drawTargets();
  }
  function defenseOptions(t) {
    const o = cur(), out = [option('', 'Defends normally')];
    const melee = !!o.melee, spell = !!o.spell, direct = !!o.direct;
    for (const [k, it] of Object.entries(RULES.interrupts)) {
      const dice = t.info && t.info.defense ? t.info.defense[k] : 0;
      let why = '';
      if (o.matrix && k !== 'full_defense') why = 'not in the Matrix';
      else if (spell && direct && k !== 'full_defense') why = 'not vs direct spells';
      else if (it.vs === 'melee' && !melee) why = 'melee only';
      else if (it.vs === 'ranged' && melee) why = 'ranged only';
      else if (t.info && t.info.inCombat) {
        const left = it.cost === 'major' ? t.info.majorLeft : t.info.minorLeft;
        const any = (t.info.majorLeft || 0) + (t.info.minorLeft || 0);
        if (!left && !(it.cost === 'minor' && t.info.majorLeft) && !(it.cost === 'major' && t.info.minorLeft >= RULES.minorPerMajor) && !ignoreActions.checked) why = any ? `no ${it.cost} action left` : 'no actions left';
      }
      if (k === 'full_defense' && t.info && t.info.fullDefense) why = 'already active';
      const nm = o.matrix && k === 'full_defense' ? 'Full Matrix Defense' : it.name;
      out.push(h('option', { value: k, disabled: !!why, title: it.desc }, `${nm} (+${o.matrix && k === 'full_defense' ? 'Firewall' : dice + ' dice'}, ${it.cost === 'major' ? 'Major' : 'Minor'})${why ? ` · ${why}` : ''}`));
    }
    return out;
  }
  function sightText(sg) {
    if (!sg) return h('span.hint', 'not on this map');
    if (!sg.los) return h('span.bad', 'No line of sight');
    return sg.cover ? h('span.warn', `Cover ${'I II III IV'.split(' ')[sg.cover - 1]} from the map`) : h('span.good', 'Clear line of sight');
  }
  function drawTargets() {
    tgtBox.innerHTML = '';
    const o = cur();
    targets.forEach((t, i) => {
      const c = pos(t.key);
      const def = h('select', { onchange: e => { t.defense = e.target.value; drawTargets(); } }, defenseOptions(t));
      def.value = t.defense; if (def.value !== t.defense) t.defense = '';
      const cov = h('select', { title: 'Cover: from the map, or set it yourself', onchange: e => { t.cover = e.target.value; describe(); } },
        option('auto', 'Cover: auto'), option('0', 'No cover'), ['I', 'II', 'III', 'IV'].map((r, j) => option(String(j + 1), `Cover ${r}`)));
      cov.value = t.cover;
      const st = t.info && t.info.statuses ? Object.keys(t.info.statuses) : [];
      const DEA = RULES.defenseEdgeActions || {};
      const dea = Object.entries(DEA).find(([, a]) => a.with === t.defense);
      if (!dea) t.edgeAction = '';
      const deaBox = dea ? h('label.check', { title: dea[1].desc }, h('input', { type: 'checkbox', checked: t.edgeAction === dea[0],
        onchange: ev => { t.edgeAction = ev.target.checked ? dea[0] : ''; describe(); } }), `${dea[1].name} (${dea[1].edge} Edge${t.info ? `, has ${t.info.edge}` : ''})`) : null;
      tgtBox.append(h('div.attack-target',
        h('div.at-name', h('span.dot', { style: { background: c ? c.color : '#888' } }), h('b', c ? c.name : t.key),
          h('span.hint', ` DR ${t.info ? (o.astral ? t.info.astralDr : o.matrix ? t.info.matrixDr : t.info.dr) : '–'}`), t.info && t.info.fullDefense ? h('span.tag', 'Full Defense') : null,
          t.info && t.info.counterspell && o.spell ? h('span.tag', { title: `Counterspell by ${t.info.counterspell[0]}` }, `+${t.info.counterspell[1]} vs spells`) : null,
          t.info && t.info.restrained ? h('span.tag', { title: 'Restrained: −4 on Defense tests; you gain Edge; a miss may hit whoever holds them' }, 'Restrained') : null,
          t.info && t.info.tacticalRoll ? h('span.tag', { title: 'Tactical Roll: no −2 from Prone against Close or Near attacks' }, 'Tactical Roll') : null,
          st.length ? h('span.hint', ' · ' + st.join(', ')) : null),
        h('div.at-sight', o.astral ? h('span.hint', 'astral: no line of sight needed') : o.matrix ? h('span.hint', 'Matrix: no line of sight needed') : sightText(t.sight)),
        h('div.at-def', def, deaBox), o.astral || o.matrix ? null : cov,
        targets.length > 1 ? h('button.small.ghost', { type: 'button', title: 'Remove this target', onclick: () => { targets.splice(i, 1); drawTargets(); describe(); } }, '✕') : null));
    });
    addSel.innerHTML = '';
    addSel.append(option('', targets.length ? '+ Add a target (Multiple Attacks)…' : 'Pick a target…'));
    for (const c of list) if (optKey(c) !== attSel.value && !targets.some(t => t.key === optKey(c))) addSel.append(option(optKey(c), c.name + (dead(c) ? ' (dead)' : '')));
    anticip.disabled = targets.length < 2;
    describe();
  }
  addSel.onchange = () => { const v = addSel.value; addSel.value = ''; addTarget(v); };
  function drawModes() {
    const o = cur();
    mode.innerHTML = '';
    (o.modes || []).forEach(m => mode.append(option(m, `${m} · ${SR.CAT.store.firingModes[m].name}`)));
    mode.disabled = !(o.modes || []).length;
    amp.disabled = !o.spell;
    astType.disabled = !o.astral; astLabel.hidden = !o.astral;
    for (const opt of eaSel.options) { const ea = (RULES.edgeActions || {})[opt.value]; if (ea) opt.disabled = (ea.melee && !o.melee) || (ea.ranged && o.melee) || (ea.cover && (attOpts.cover || 0) < ea.cover); }
    if (eaSel.selectedOptions[0] && eaSel.selectedOptions[0].disabled) eaSel.value = '';
    anticip.title = RULES.anticipation.desc;
    intercept.disabled = !o.melee;
    if (!o.melee) intercept.checked = false;
    const ranged = !o.melee && !o.spell && !o.astral && !o.matrix;
    aimNow.disabled = !ranged || !!attOpts.aimedThisRound; if (aimNow.disabled) aimNow.checked = false;
    aimInfo.textContent = ranged ? (attOpts.aim ? `Aiming: +${attOpts.aim} (up to ${attOpts.aimMax})` : '') + (attOpts.aimedThisRound ? ' · already aimed this round' : '') : '';
    trip.disabled = !o.melee; if (!o.melee) trip.checked = false;
    const unarmed = !!o.melee && /unarmed/i.test(o.key + ' ' + o.name) && !o.astral;
    grapple.disabled = !unarmed; if (!unarmed) grapple.checked = false;
    drawTargets();
  }
  function describe() {
    const o = cur(); if (!o.key) { info.textContent = ''; return; }
    const i = SR.RANGES.indexOf(range.value), fm = mode.value && !mode.disabled ? SR.CAT.store.firingModes[mode.value] : null;
    let ar = o.ar ? o.ar[i] : null;
    if (ar != null && fm) ar = Math.max(0, ar + fm.ar);
    const cs = RULES.calledShots[called.value];
    const n = targets.length || 1;
    let pool = o.pool + (cs ? cs.dice : 0);
    const ranged = !o.melee && !o.spell && !o.astral && !o.matrix;
    const aim = ranged ? Math.min(attOpts.aimMax || 1, (attOpts.aim || 0) + (aimNow.checked ? 1 : 0)) : 0;
    pool += aim;
    if (n > 1 && !anticip.checked) pool = Math.floor(pool / n);
    const ea = (RULES.edgeActions || {})[eaSel.value];
    const edge = (cs ? cs.edge : 0) + (n > 1 && anticip.checked ? RULES.anticipation.edge : 0) + (ea ? ea.edge : 0);
    const acts = ['1 Major'].concat(intercept.checked ? ['1 Minor (Intercept)'] : [], n > 1 && mode.value !== 'FA' ? ['1 Minor (Multiple Attacks)'] : [],
      cs && cs.minor ? ['1 Minor (called shot)'] : [], attOpts.cover && !o.astral && !o.matrix ? ['1 Minor (out of cover)'] : [],
      trip.checked ? ['1 Minor (Trip)'] : [], aimNow.checked ? ['1 Minor (Take Aim)'] : []);
    if (attOpts.cover === 4 && !o.astral && !o.matrix && eaSel.value !== 'fire_from_cover') pool -= 2;
    const rounds = fm ? (mode.value === 'FA' ? fm.rounds : fm.rounds * n) : 0;
    const parts = [];
    if (o.astral && targets[0] && targets[0].info) {
      const dr = targets[0].info.astralDr, diff = ar - dr;
      parts.push(`Astral: AR ${ar} vs DR ${dr}` + (diff >= 4 ? ' → attacker gains 1 Edge' : diff <= -4 ? ' → defender gains 1 Edge' : '') + '; defense Intuition + Logic');
    } else if (ar == null && !o.spell) parts.push(`Can’t attack at ${range.value} range with this.`);
    else if (targets[0] && targets[0].info) {
      const t0 = targets[0], cov = o.matrix ? 0 : t0.cover === 'auto' ? (t0.sight ? t0.sight.cover : 0) : +t0.cover;
      const dr = (o.matrix ? (t0.info.matrixDr || 0) : t0.info.dr) + cov, diff = ar - dr;
      parts.push(`AR ${ar} vs DR ${dr}${cov ? ` (cover +${cov})` : ''}` + (diff >= 4 && !attOpts.cover ? ' → attacker gains 1 Edge' : diff <= -4 ? ' → defender gains 1 Edge' : ''));
    }
    parts.push(`${pool} dice${n > 1 ? ` per target (${n} targets)` : ''}`);
    if (o.clip) parts.push(`${o.loaded}/${o.clip} loaded${rounds ? `, uses ${rounds}` : ''}`);
    else if (o.qty) parts.push(`${o.qty} left`);
    if (o.spell) parts.push(`drain ${o.drain}${+amp.value ? ' + ' + 2 * amp.value : ''}`);
    if (edge) parts.push(`costs ${edge} Edge (has ${attOpts.edge ?? '?'})` + (attOpts.edgeSpent ? ' · already spent Edge this round' : ''));
    if (attOpts.inCombat) parts.push(`uses ${acts.join(' + ')} · ${attOpts.majorLeft} Major / ${attOpts.minorLeft} Minor left`);
    if (attOpts.dirt) parts.push('−2 dice (Hit the Dirt)');
    if (aim) parts.push(`+${aim} Take Aim`);
    if (trip.checked) parts.push('Trip: −2 DV; on a hit they test Athletics + Agility or fall');
    if (grapple.checked) parts.push('Grapple: no damage; Strength + net hits vs Strength to hold them');
    const defEdge = targets.filter(t => t.edgeAction).map(t => `${(pos(t.key) || {}).name}: ${RULES.defenseEdgeActions[t.edgeAction].name}`);
    if (defEdge.length) parts.push(defEdge.join(', '));
    info.textContent = parts.join(' · ');
  }
  attSel.onchange = () => { const k = attSel.value; const i = targets.findIndex(t => t.key === k); if (i >= 0) targets.splice(i, 1); loadAttacker(); };
  weapon.onchange = () => { picked = true; drawModes(); };
  for (const el of [mode, range, amp, called, anticip, eaSel, intercept, aimNow, trip, grapple]) el.addEventListener('change', describe);
  ignoreActions.onchange = drawTargets;
  const body = h('div',
    h('div.form-grid', h('label', 'Attacker', attSel), h('label', 'Weapon / spell', weapon), h('label', 'Firing mode', mode),
      h('label', h('span', 'Range ', distInfo), range)),
    attInfo,
    h('h3.mt', 'Targets'), tgtBox, addSel,
    info,
    h('div.form-grid.mt', h('label', 'Called shot', called), h('label', 'Edge action', eaSel), astLabel),
    h('div.row', h('label.check', { title: RULES.anticipation.desc }, anticip, `Anticipation (${RULES.anticipation.edge} Edge)`),
      h('label.check', { title: RULES.intercept.desc }, intercept, 'Intercept (out of turn)'),
      h('label.check', { title: RULES.takeAim.desc }, aimNow, 'Take Aim first (Minor)'), aimInfo,
      h('label.check', { title: RULES.trip.desc }, trip, 'Trip (Minor)'),
      h('label.check', { title: 'Unarmed: on a hit, Strength + net hits vs their Strength to hold them (no damage)' }, grapple, 'Grapple')),
    h('details', h('summary', 'Modifiers'), h('div.form-grid', h('label', 'Attack dice ±', amod), h('label', 'Defense dice ±', dmod), h('label', 'Soak dice ±', smod),
      h('label', 'Extra DV', xdv), h('label', 'Amp Up (spells)', amp), h('label', 'NPC dice (override)', dice), h('label', 'Meters per cell', meters))),
    h('div.row', h('label.check', wild, 'Wild Die'), h('label.check', { title: 'Optional rule for grunts below PR 3: they don’t roll to defend' }, unopp, 'Unopposed (grunt)'),
      h('label.check', hidden, 'Hidden roll'), h('label.check', apply, 'Apply damage'),
      h('label.check', { title: 'Give 1 Edge to whoever wins AR vs DR by 4+ (the highest DR with several targets), at most 2 per round; none when attacking from cover' }, autoEdge, 'Award Edge'),
      h('label.check', { title: 'Indirect fire, scent, sound…' }, ignoreSight, 'Ignore line of sight'),
      h('label.check', { title: 'Allow the attack even without actions left this round' }, ignoreActions, 'Ignore action limits')));
  const okP = UI.modal('Attack', body, { ok: 'Roll attack', wide: true, onOpen: async () => { if (firstTarget) await addTarget(firstTarget); await loadAttacker(); } });
  if (!await okP) return;
  if (!targets.length) { toast('Pick a target.'); return; }
  const defenses = {}, cover = {}, wrest = {}, tactical = {};
  for (const t of targets) {
    if (t.defense) defenses[t.key] = t.defense; cover[t.key] = t.cover === 'auto' ? 'auto' : +t.cover;
    if (t.edgeAction === 'wrest') wrest[t.key] = true;
    if (t.edgeAction === 'tactical_roll') tactical[t.key] = true;
  }
  try {
    const r = await api(`/api/maps/${MAP_ID}/attack`, 'POST', { attacker: refOf(attSel.value), targets: targets.map(t => refOf(t.key)), weapon: weapon.value,
      mode: mode.disabled ? null : mode.value, range: range.value, attackMod: +amod.value || 0, defenseMod: +dmod.value || 0, soakMod: +smod.value || 0,
      extraDv: +xdv.value || 0, amp: +amp.value || 0, dice: dice.value === '' ? null : +dice.value, wild: wild.checked, hidden: hidden.checked,
      unopposed: unopp.checked, apply: apply.checked, defenses, cover, called: called.value || null, anticipation: anticip.checked,
      intercept: intercept.checked, edgeAction: eaSel.value || null, astralType: astType.value, autoEdge: autoEdge.checked,
      ignoreSight: ignoreSight.checked, ignoreActions: ignoreActions.checked, aimNow: aimNow.checked, trip: trip.checked, grapple: grapple.checked, wrest, tactical });
    toast(r.results.map(x => x.summary).join(' '), 7000);
    renderRolls(r.rolls);
    await reloadContext();
  } catch (e) { toast(e.message, 6000); }
}

// ------------------------------------------------------------ legend
function renderLegend() {
  const el = $('legend'); el.hidden = !S.map.settings.legendVisible; el.innerHTML = '';
  if (el.hidden) return;
  const view = currentView(), vis = k => GridCore.visibility(view, k, cells()[k]);
  const groups = new Map(), doors = new Map();
  for (const m of markers()) { if (vis(key(m.c, m.r)) !== 'full') continue; const k = m.type + '|' + (m.color || colors().markerDefault); groups.set(k, (groups.get(k) || 0) + 1); }
  for (const k in cells()) { const cell = cells()[k]; if (!cell || !cell.doors || vis(k) === 'hidden') continue; for (const e in cell.doors) { const c = cell.doors[e].color; doors.set(c, (doors.get(c) || 0) + 1); } }
  const tokens = view.tokens || [];
  if (!groups.size && !doors.size && !tokens.length) return;
  const h = document.createElement('h4'); h.textContent = 'Legend'; el.appendChild(h);
  const addRow = (iconEl, text, count) => { const row = document.createElement('div'); row.className = 'legend-row'; const sp = document.createElement('span'); sp.textContent = text; const ct = document.createElement('span'); ct.className = 'count'; ct.textContent = count; row.append(iconEl, sp, ct); el.appendChild(row); };
  for (const [k, n] of groups) { const [type, color] = k.split('|'); const cv = document.createElement('canvas'); cv.width = 36; cv.height = 36; drawMarker(cv.getContext('2d'), 18, 18, 26, type, color, colors().markerText, false); addRow(cv, (MARKER_BY_ID[type] || MARKER_TYPES[0]).name, '×' + n); }
  for (const [color, n] of doors) { const sw = document.createElement('span'); sw.className = 'sw'; sw.style.background = color; addRow(sw, 'Door', '×' + n); }
  for (const t of tokens) { const cv = document.createElement('canvas'); cv.width = 36; cv.height = 36; GridCore.drawToken(cv.getContext('2d'), 18, 18, 28, t, colors(), false); addRow(cv, t.name, ''); }
}

// ------------------------------------------------------------ settings dialog
const COLOR_LABELS = {
  background: 'Background', grid: 'Grid lines', fog: 'Fog (play mode)', cellDefault: 'Default cell', cellBorder: 'Default cell border',
  exploredTint: 'Explored tint', revealedTint: 'Map-station tint', secretHatch: 'Secret hatching', markerDefault: 'Default marker',
  markerText: 'Marker glyph', doorDefault: 'Default door', doorOpen: 'Open-door highlight', highlight: 'Cursor highlight',
  roomLabel: 'Room names', tokenOutline: 'Own token outline',
};
function openSettings() {
  const grid = $('settings-colors'); grid.innerHTML = '';
  for (const k in COLOR_LABELS) {
    const lab = document.createElement('label'); lab.textContent = COLOR_LABELS[k] + ' ';
    const inp = document.createElement('input'); inp.type = 'color'; inp.value = colors()[k];
    inp.oninput = () => { colors()[k] = inp.value; markDirty(); renderLegend(); renderMarkerTypes(); };
    lab.appendChild(inp); grid.appendChild(lab);
  }
  const pal = $('settings-door-palette'); pal.innerHTML = '';
  S.map.settings.doorPalette.forEach((c, i) => { const inp = document.createElement('input'); inp.type = 'color'; inp.value = c; inp.oninput = () => { S.map.settings.doorPalette[i] = inp.value; markDirty(); renderDoorSwatches(); }; pal.appendChild(inp); });
  const sc = $('set-campaign'); sc.innerHTML = '<option value="">No game</option>';
  for (const cp of S.ctx.campaigns || []) { const o = document.createElement('option'); o.value = cp.id; o.textContent = cp.name; sc.appendChild(o); }
  sc.value = S.map.campaignId || '';
  $('set-grid').checked = !!S.map.settings.showGrid;
  $('set-sight').checked = !!S.map.settings.sightReveal; $('set-sight-r').value = S.map.settings.sightRadius || 8;
  $('set-w').value = S.map.width; $('set-h').value = S.map.height; $('set-cs').value = S.map.cellSize;
  $('settings-dialog').showModal();
}
$('btn-settings').onclick = openSettings;
$('set-grid').onchange = e => { S.map.settings.showGrid = e.target.checked; markDirty(); };
$('set-sight').onchange = e => { S.map.settings.sightReveal = e.target.checked; markDirty(); };
$('set-sight-r').onchange = e => { S.map.settings.sightRadius = Math.max(1, Math.min(20, +e.target.value || 8)); e.target.value = S.map.settings.sightRadius; markDirty(); };
$('set-w').onchange = e => { S.map.width = Math.max(4, Math.min(200, +e.target.value || 4)); markDirty(); };
$('set-h').onchange = e => { S.map.height = Math.max(4, Math.min(200, +e.target.value || 4)); markDirty(); };
$('set-cs').onchange = e => { S.map.cellSize = Math.max(8, Math.min(128, +e.target.value || 8)); markDirty(); };
$('set-campaign').onchange = async e => { S.map.campaignId = e.target.value || null; await saveMap(); await reloadContext(); toast('Game updated.'); };
$('set-delete').onclick = async () => {
  const here = (S.ctx.players || []).filter(p => p.currentMapId === MAP_ID);
  const who = here.length ? ` ${here.map(p => p.name).join(', ')} will be taken off it.` : '';
  $('settings-dialog').close();
  if (!await UI.confirm(`Delete the map "${S.map.name}"? This can't be undone.${who}`, { danger: true, ok: 'Delete map' })) return;
  S.deleted = true;
  try { await api(`/api/maps/${MAP_ID}`, 'DELETE'); location.href = S.map.campaignId ? `/game/${S.map.campaignId}#maps` : '/'; }
  catch (e) { S.deleted = false; toast(e.message); }
};
$('set-reset').onclick = async () => {
  const d = await api('/api/defaults');
  S.map.settings.colors = d.colors; S.map.settings.doorPalette = d.doorPalette;
  markDirty(); openSettings(); renderDoorSwatches(); renderMarkerTypes(); renderLegend();
};

// ------------------------------------------------------------ export
$('btn-export-json').onclick = async () => { await saveMap(); location.href = `/api/maps/${MAP_ID}/export`; };
$('btn-export-png').onclick = () => {
  const d = $('export-dialog'); d.returnValue = '';
  $('ex-grid').checked = !!S.map.settings.showGrid; $('ex-rooms').checked = S.map.settings.showRoomLabels !== false;
  $('ex-view').textContent = S.mode === 'edit' ? 'Exports everything (edit view).' : player() ? `Exports ${player().name}'s view.` : 'Exports the GM view with tokens.';
  d.onclose = () => { if (d.returnValue === 'ok') exportPng(); };
  d.showModal();
};
function exportPng() {
  const pixel = false, scale = +$('ex-scale').value, view = currentView();
  const opts = { forExport: true, grid: $('ex-grid').checked, borders: $('ex-borders').checked, roomNames: $('ex-rooms').checked };
  const b = paintedBounds(S.map, 1), { w, h } = G().mapPixelSize();
  const out = document.createElement('canvas'); out.width = Math.ceil(b.w * scale); out.height = Math.ceil(b.h * scale);
  const g = out.getContext('2d');
  const full = document.createElement('canvas');
  const q = pixel ? 1 : Math.max(1, scale);
  full.width = Math.ceil(w * q); full.height = Math.ceil(h * q);
  const fg = full.getContext('2d'); fg.scale(q, q);
  renderScene(fg, S.map, view, { ...opts, pixel });
  if ($('ex-transparent').checked) {   // punch out the background/fog color
    const bg = view.mode === 'edit' ? colors().background : colors().fog, [br, bgc, bb] = [parseInt(bg.slice(1, 3), 16), parseInt(bg.slice(3, 5), 16), parseInt(bg.slice(5, 7), 16)];
    const img = fg.getImageData(0, 0, full.width, full.height), px = img.data;
    for (let i = 0; i < px.length; i += 4) if (Math.abs(px[i] - br) < 3 && Math.abs(px[i + 1] - bgc) < 3 && Math.abs(px[i + 2] - bb) < 3) px[i + 3] = 0;
    fg.setTransform(1, 0, 0, 1, 0, 0); fg.putImageData(img, 0, 0);
  }
  g.imageSmoothingEnabled = !pixel;
  g.drawImage(full, b.x * q, b.y * q, b.w * q, b.h * q, 0, 0, out.width, out.height);
  out.toBlob(blob => {
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    const suffix = S.mode === 'edit' ? '' : player() ? ` (${player().name}'s view)` : ' (GM view)';
    a.download = `${S.map.name.replace(/[^\w\- ]+/g, '_')}${suffix}.png`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }, 'image/png');
}

// ------------------------------------------------------------ dice (Shadowrun pools, shared table log)
function renderRolls(rolls) {
  SR.renderLog($('roll-log'), rolls);
  const r = (rolls || [])[0];
  $('dock-last').textContent = r ? 'Last: ' + SR.rollSummary(r) : '';
}
async function rollDice(n) {
  if (!S.ctx.campaign) { toast('Dice need a game (so players can see the rolls).'); return; }
  const body = { dice: n || +$('dice-n').value, label: $('dice-label').value.trim(), wild: $('dice-wild').checked, threshold: +$('dice-thr').value || 0, hidden: $('dice-hidden').checked };
  try { const r = await api(`/api/games/${S.ctx.campaign.id}/roll`, 'POST', body); renderRolls(r.rolls); }
  catch (e) { toast(e.message); }
}
$('dice-roll').onclick = () => rollDice();
$('dice-label').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); rollDice(); } });
for (const n of [4, 8, 12]) $('dice-quick').append(h('button.small', { type: 'button', onclick: () => rollDice(n) }, n + 'd'));

// ------------------------------------------------------------ context load / polling
function applyContext(c, full) {
  S.version = c.version;
  const mapSame = !c.map || c.map.data == null;      // the server left the map out: ours is current
  if (!mapSame) S.mapSig = c.mapSig;
  if (c.now) S.clockSkew = Date.now() / 1000 - c.now;
  if (c.rolls) renderRolls(c.rolls);
  S.ctx.campaignMaps = c.campaignMaps; S.ctx.snapshots = c.snapshots; S.ctx.campaign = c.campaign; S.ctx.allMaps = c.allMaps; if (c.vehicles) S.ctx.vehicles = c.vehicles;
  for (const np of c.players) { if (S.fogQueue && S.fogQueue.pid === np.id) continue; const lp = S.ctx.players.find(p => p.id === np.id); if (lp) Object.assign(lp, np); else S.ctx.players.push(np); }
  S.ctx.players = S.ctx.players.filter(p => c.players.some(np => np.id === p.id));
  if (mapSame) { /* nothing changed on the map */ }
  else if (full) S.map.data = c.map.data;
  else {
    // live state changed elsewhere (players opening doors, combat damage, statuses) wins unless the editor changed it itself
    for (const k in c.map.data.cells) { const nc = c.map.data.cells[k], lc = cells()[k]; if (lc && lc.doors && nc.doors) for (const e in lc.doors) if (nc.doors[e] && !S.rt.all && !S.rt.doors.has(`${k}:${e}`)) { lc.doors[e].open = nc.doors[e].open; if (nc.doors[e].locked) lc.doors[e].locked = true; else delete lc.doors[e].locked; } }
    const byId = Object.fromEntries(c.map.data.markers.map(m => [m.id, m]));
    for (const m of markers()) {
      const sm = byId[m.id]; if (!sm || S.rt.all || S.rt.markers.has(m.id)) continue;
      for (const k of ['cm', 'statuses', 'npc']) { if (k === 'npc' && S.mode === 'edit' && S.dirty) continue; if (sm[k]) m[k] = sm[k]; else delete m[k]; }
      if (S.mode === 'play') { m.c = sm.c; m.r = sm.r; m.label = sm.label; if (sm.hidden) m.hidden = true; else delete m.hidden; }
    }
  }
  S.tracker = c.tracker; renderCombat();
  renderPlayers(); renderSnapshots(); renderLinkMaps(); renderLegend(); invalidate();
  if (S.selected) renderInspector();
  const p = player();
  if (S.follow && p && p.currentMapId && p.currentMapId !== MAP_ID) location.href = `/map/${p.currentMapId}?view=${encodeURIComponent(p.id)}&follow=1`;
}
async function reloadContext(full) { applyContext(await api(`/api/maps/${MAP_ID}/context`), full); }
/* live updates (SSE) trigger poll() on every change; the timer is only a fallback while the stream is down */
function schedulePoll(ms) { clearTimeout(S.pollTimer); S.pollInterval = ms; S.pollTimer = setTimeout(poll, Live.connected() ? Math.max(ms, 20000) : ms); }
async function poll() {
  if (!document.hidden) {
    try { const c = await api(`/api/maps/${MAP_ID}/context?since=${encodeURIComponent(S.version || '')}&map=${encodeURIComponent(S.mapSig || '')}`); if (!c.unchanged) applyContext(c, false); }
    catch (e) { /* transient */ }
  }
  schedulePoll(S.pollInterval);
}
document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
Live.on(() => poll());
Music.mount({ gm: true, map: MAP_ID, host: document.querySelector('.topbar-actions') });

// ------------------------------------------------------------ boot
async function boot() {
  Layout.init($('layout'), 'gm');
  const [c, ov] = await Promise.all([api(`/api/maps/${MAP_ID}/context`), api('/api/overview'), SR.catalog()]);
  S.map = c.map;
  S.ctx = { players: c.players, campaigns: ov.campaigns, campaignMaps: c.campaignMaps, snapshots: c.snapshots, campaign: c.campaign, allMaps: c.allMaps, vehicles: c.vehicles || [] };
  S.version = c.version; S.mapSig = c.mapSig; if (c.now) S.clockSkew = Date.now() / 1000 - c.now;
  document.title = S.map.name + ' · ShadowGrid';
  $('map-name').value = S.map.name;
  if (c.campaign) { $('back-link').href = `/game/${c.campaign.id}#maps`; $('back-link').textContent = '‹ ' + c.campaign.name; }
  $('paint-color').value = colors().cellDefault; $('paint-border').value = colors().cellBorder;
  $('door-color').value = S.map.settings.doorPalette[0] || colors().doorDefault;
  $('marker-color').value = colors().markerDefault;
  $('legend-toggle').checked = S.map.settings.legendVisible !== false;
  $('rooms-toggle').checked = S.map.settings.showRoomLabels !== false;
  renderPaintSwatches(); renderDoorSwatches(); renderMarkerTypes(); renderLinkMaps(); renderRoomList(); renderSnapshots(); renderTemplateSelect();
  S.tracker = c.tracker;
  $('link-id').value = newLinkId();
  if (c.rolls) renderRolls(c.rolls);
  const q = new URLSearchParams(location.search);
  if (q.get('view')) { setMode('play'); setViewAs(q.get('view')); S.follow = q.get('follow') === '1'; $('follow-player').checked = S.follow; history.replaceState(null, '', location.pathname); }
  else if (q.get('play')) { setMode('play'); history.replaceState(null, '', location.pathname); }
  else setMode('edit');
  if (fpPref()) setFp(true);
  try { if (localStorage.getItem('sg.los.gm') === '1') { S.los = true; $('los-toggle').checked = true; $('los-key').hidden = false; } } catch { /* ignore */ }
  vp.fit(); invalidate();
}
new ResizeObserver(() => requestDraw()).observe(wrap);
window.addEventListener('beforeunload', e => { flushFog(); if (S.dirty) { e.preventDefault(); e.returnValue = ''; } });
boot().catch(e => { if (e.message !== 'auth') toast('Could not load the map: ' + e.message); });
// handle for automated UI tests
window.__sg = { S, vp, G, markerAt, canvas };
})();
