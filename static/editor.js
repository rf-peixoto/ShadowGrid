/* GridMap GM editor (ShadowGrid). Depends on api.js, gridcore.js and srui.js. */
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
  version: null, pollTimer: null, pollInterval: 6000, playersSig: '', rollsSig: '', follow: false, pingFrame: null, iso: {}, sceneIso: null,
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
    if (t) tokens.push({ c: t.c, r: t.r, color: p.color, name: p.name, me: p.id === S.viewAs, cm: p.cm });
  }
  const p = player();
  if (!p) return { mode: 'gm', tokens, rooms: showRooms };
  const ms = pms(p);
  return { mode: 'player', explored: new Set(Object.keys(ms.explored)), mapStation: !!ms.mapStation, tokens };
}
function hoverLabel() {
  if (!S.hover) return null;
  const m = markerAt(S.hover.c, S.hover.r), parts = [];
  if (m && m.label) parts.push(m.label);
  if (m && m.linkId) { const t = m.target && S.ctx.allMaps.find(x => x.id === m.target.mapId); parts.push('→ ' + (t ? t.name : 'by ID ' + m.linkId)); }
  const rm = roomOf(key(S.hover.c, S.hover.r));
  if (rm && S.map.settings.showRoomLabels === false) parts.push(rm.name);
  return parts.length ? { c: S.hover.c, r: S.hover.r, text: parts.join(' · ') } : null;
}

// ------------------------------------------------------------ drawing (scene cached; overlays per frame)
function invalidate() { S.sceneDirty = true; requestDraw(); }
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
  markDirty(); renderRoomList(); renderRoomSelects(); renderLegend(); if (S.selected) renderInspector();
}

// ------------------------------------------------------------ persistence (map)
function markDirty() {
  S.dirty = true; $('save-state').textContent = 'Unsaved';
  clearTimeout(S.saveTimer); S.saveTimer = setTimeout(saveMap, 700);
  invalidate();
}
async function saveMap() {
  if (!S.map) return;
  $('save-state').textContent = 'Saving…';
  try {
    await api(`/api/maps/${MAP_ID}`, 'PUT', { name: S.map.name, width: S.map.width, height: S.map.height, cellSize: S.map.cellSize, settings: S.map.settings, data: S.map.data, campaignId: S.map.campaignId });
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
  invalidate();
  if (S.mode === 'edit') { markDirty(); return; }
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
  if (S.mode === 'edit') { markDirty(); if (S.selected) renderInspector(); return; }
  try { const res = await api(`/api/maps/${MAP_ID}/door`, 'POST', lock ? { c, r, edge: e, locked: d.locked } : { c, r, edge: e, open: d.open }); d.open = res.open; d.locked = res.locked; }
  catch (err) { Object.assign(d, before); toast(err.message); }
  invalidate(); if (S.selected) renderInspector();
}
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
  return { pm: body > 0 ? 8 + Math.ceil(body / 2) : 0, sm: wil > 0 ? 8 + Math.ceil(wil / 2) : 0, ov: body > 0 ? body : 0, p: 0, s: 0 };
}
function cmHint() {
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
  if (ev.button === 1 || ev.button === 2 || S.spaceDown) { S.dragging = { kind: 'pan', sx, sy, px: vp.panX, py: vp.panY }; canvas.classList.add('panning'); return; }
  if (ev.button !== 0) return;
  const pt = vp.screenToMap(sx, sy), cell = G().pointToCell(pt.x, pt.y);
  if (S.tool === 'rect') { if (cell) { pushUndo(); S.dragging = { kind: 'rect', start: cell }; } return; }
  if (S.tool === 'room') { if (cell) { pushUndo(); S.dragging = { kind: 'room', start: cell, set: new Set([key(cell.c, cell.r)]) }; } requestDraw(); return; }
  if ((S.tool === 'marker' || S.tool === 'pmarker') && cell && markerAt(cell.c, cell.r)) { S.dragging = { kind: 'marker', m: markerAt(cell.c, cell.r), from: cell, moved: false }; return; }
  S.shiftDown = ev.shiftKey;
  S.dragging = { kind: 'apply', last: null };
  if (cell) { applyTool(cell, pt, true); S.dragging.last = key(cell.c, cell.r); }
  requestDraw();
});
canvas.addEventListener('pointermove', ev => {
  const { sx, sy } = vp.canvasPoint(ev), pt = vp.screenToMap(sx, sy);
  S.hoverPt = pt; S.hover = G().pointToCell(pt.x, pt.y);
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
canvas.addEventListener('wheel', ev => { ev.preventDefault(); const { sx, sy } = vp.canvasPoint(ev); vp.zoomAt(sx, sy, Math.exp(-ev.deltaY * 0.0015)); requestDraw(); }, { passive: false });

// ------------------------------------------------------------ keyboard
const TOOL_KEYS = { edit: { p: 'paint', r: 'rect', e: 'erase', s: 'secret', d: 'door', m: 'marker', g: 'room', v: 'select' },
                    play: { p: 'reveal', e: 'hide', d: 'pdoor', t: 'token', m: 'pmarker', v: 'select' } };
window.addEventListener('keydown', ev => {
  if (ev.target.matches('input, textarea, select, [contenteditable]') || document.querySelector('dialog[open]')) return;
  if (ev.code === 'Space') { S.spaceDown = true; canvas.classList.add('panning'); ev.preventDefault(); return; }
  const k = ev.key.toLowerCase();
  if ((ev.ctrlKey || ev.metaKey) && k === 'z') { ev.preventDefault(); undo(); return; }
  if (ev.ctrlKey || ev.metaKey) return;
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
  document.querySelectorAll('.tool-group[data-mode]').forEach(g => g.hidden = g.dataset.mode !== m);
  setTool(m === 'edit' ? 'paint' : 'reveal');
  if (isoPref(m) !== vp.iso) setIso(isoPref(m), false);
  { const g = document.querySelector(`.tool-group[data-mode="${m}"]`), before = g.querySelector('.fog-actions'); before ? g.insertBefore($('inspector'), before) : g.appendChild($('inspector')); }
  S.selected = null;
  renderInspector(); renderPlayers(); renderLegend(); invalidate();
  schedulePoll(m === 'play' ? 1500 : 6000);
}
$('mode-edit').onclick = () => setMode('edit');
$('mode-play').onclick = () => setMode('play');
function setViewAs(id) { flushFog(); S.viewAs = id; renderViewAs(); refreshFogPanel(); renderInspector(); renderLegend(); invalidate(); }
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
  $('reveal-hint').textContent = p ? `Drag to change what ${p.name} has explored.` : 'Pick a player above to use the Reveal and Hide brushes.';
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
const RECENT_KEY = 'gridmap.recentColors';
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
  $('no-campaign').hidden = hasCampaign; $('players-panel').hidden = !hasCampaign; $('snapshots-panel').hidden = !hasCampaign; $('dice-panel').hidden = !hasCampaign;
  if (S.viewAs && !S.ctx.players.some(p => p.id === S.viewAs)) S.viewAs = '';
  renderViewAs(); refreshFogPanel();
  const sig = JSON.stringify(S.ctx.players.map(p => [p.id, p.name, p.color, p.radius, p.currentMapId, p.cm, p.edge, p.status]));
  if (sig === S.playersSig || $('player-list').contains(document.activeElement)) return;
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
    el.append(h('div.player-row',
      h('div.row.tight', { style: { flexWrap: 'nowrap' } }, sw, h('a.grow', { href: `/game/${S.ctx.campaign.id}/sheet/${p.id}`, target: '_blank', title: 'Open the character sheet' }, p.name), rad),
      p.status !== 'approved' ? h('div', SR.statusTag(p.status)) : null,
      cmLine,
      h('div.row.tight.between', h('span.hint', here ? 'On this map' : elsewhere ? `On ${elsewhere.name}` : 'Not placed'),
        h('span.row.tight',
          here ? h('button.small', { type: 'button', title: 'Take the token off this map', onclick: async () => { await api(`/api/players/${p.id}/unplace`, 'POST', {}); reloadContext(); } }, 'Unplace') : null,
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
  if (!S.selected) { box.hidden = true; return; }
  const { c, r } = S.selected, cell = getCell(c, r), p = player();
  const wasHidden = box.hidden;
  box.hidden = false;
  if (wasHidden) requestAnimationFrame(() => box.scrollIntoView({ block: 'nearest', behavior: 'smooth' }));
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
    row.appendChild(markerCM(m));
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
      if (S.mode === 'edit') { pushUndo(); const k = track === 'stun' ? 's' : 'p'; m.cm[k] = Math.max(0, m.cm[k] + n); if (k === 's' && m.cm.s > m.cm.sm) { m.cm.p += m.cm.s - m.cm.sm; m.cm.s = m.cm.sm; } markDirty(); renderInspector(); return; }
      api(`/api/maps/${MAP_ID}/marker`, 'POST', { id: m.id, damage: { track, amount: n } }).then(r => { m.cm = r.marker.cm; invalidate(); renderInspector(); }).catch(e => toast(e.message));
    };
    const set = (track, value) => dmg(track, value - (track === 'stun' ? m.cm.s : m.cm.p));
    if (m.cm.pm) box.append(SR.monitor('physical', m.cm, { onSet: set, compact: true, showTools: false }), h('div.row.tight', h('button.small', { type: 'button', onclick: () => dmg('physical', 1) }, '+1 P'), h('button.small', { type: 'button', onclick: () => dmg('physical', -1) }, 'Heal P')));
    if (m.cm.sm) box.append(SR.monitor('stun', m.cm, { onSet: set, compact: true, showTools: false }), h('div.row.tight', h('button.small', { type: 'button', onclick: () => dmg('stun', 1) }, '+1 S'), h('button.small', { type: 'button', onclick: () => dmg('stun', -1) }, 'Heal S')));
    const st = GridCore.cmStatus(m.cm);
    box.append(h('div.row.tight', SR.healthTag(st), h('button.small.ghost', { type: 'button', onclick: () => updateMarkerLive(m, { cm: null }).then(() => { delete m.cm; invalidate(); renderInspector(); }) }, 'Remove monitor')));
  } else {
    const b = h('input', { type: 'number', min: 1, max: 20, placeholder: 'Body' }), w = h('input', { type: 'number', min: 1, max: 20, placeholder: 'Wil' });
    box.append(h('div.row.tight', h('span.hint', 'Monitor:'), b, w, h('button.small', { type: 'button', onclick: () => { const cm = cmFromAttrs(+b.value, +w.value); if (!cm) { toast('Enter Body and/or Willpower.'); return; } updateMarkerLive(m, { cm }); renderInspector(); } }, 'Add')));
  }
  return box;
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
  $('set-w').value = S.map.width; $('set-h').value = S.map.height; $('set-cs').value = S.map.cellSize;
  $('settings-dialog').showModal();
}
$('btn-settings').onclick = openSettings;
$('set-grid').onchange = e => { S.map.settings.showGrid = e.target.checked; markDirty(); };
$('set-w').onchange = e => { S.map.width = Math.max(4, Math.min(200, +e.target.value || 4)); markDirty(); };
$('set-h').onchange = e => { S.map.height = Math.max(4, Math.min(200, +e.target.value || 4)); markDirty(); };
$('set-cs').onchange = e => { S.map.cellSize = Math.max(8, Math.min(128, +e.target.value || 8)); markDirty(); };
$('set-campaign').onchange = async e => { S.map.campaignId = e.target.value || null; await saveMap(); await reloadContext(); toast('Game updated.'); };
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
};

// ------------------------------------------------------------ dice (Shadowrun pools, shared table log)
function renderRolls(rolls) { SR.renderLog($('roll-log'), rolls); }
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
  if (c.now) S.clockSkew = Date.now() / 1000 - c.now;
  if (c.rolls) renderRolls(c.rolls);
  S.ctx.campaignMaps = c.campaignMaps; S.ctx.snapshots = c.snapshots; S.ctx.campaign = c.campaign; S.ctx.allMaps = c.allMaps;
  for (const np of c.players) { if (S.fogQueue && S.fogQueue.pid === np.id) continue; const lp = S.ctx.players.find(p => p.id === np.id); if (lp) Object.assign(lp, np); else S.ctx.players.push(np); }
  S.ctx.players = S.ctx.players.filter(p => c.players.some(np => np.id === p.id));
  if (full) S.map.data = c.map.data;
  else if (!S.dirty) for (const k in c.map.data.cells) { const nc = c.map.data.cells[k], lc = cells()[k]; if (lc && lc.doors && nc.doors) for (const e in lc.doors) if (nc.doors[e]) { lc.doors[e].open = nc.doors[e].open; if (nc.doors[e].locked) lc.doors[e].locked = true; else delete lc.doors[e].locked; } }
  renderPlayers(); renderSnapshots(); renderLinkMaps(); renderLegend(); invalidate();
  if (S.selected) renderInspector();
  const p = player();
  if (S.follow && p && p.currentMapId && p.currentMapId !== MAP_ID) location.href = `/map/${p.currentMapId}?view=${encodeURIComponent(p.id)}&follow=1`;
}
async function reloadContext(full) { applyContext(await api(`/api/maps/${MAP_ID}/context`), full); }
function schedulePoll(ms) { clearTimeout(S.pollTimer); S.pollInterval = ms; S.pollTimer = setTimeout(poll, ms); }
async function poll() {
  if (!document.hidden) {
    try { const c = await api(`/api/maps/${MAP_ID}/context?since=${encodeURIComponent(S.version || '')}`); if (!c.unchanged) applyContext(c, false); }
    catch (e) { /* transient */ }
  }
  schedulePoll(S.pollInterval);
}
document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });

// ------------------------------------------------------------ boot
async function boot() {
  const [c, ov] = await Promise.all([api(`/api/maps/${MAP_ID}/context`), api('/api/overview'), SR.catalog()]);
  S.map = c.map;
  S.ctx = { players: c.players, campaigns: ov.campaigns, campaignMaps: c.campaignMaps, snapshots: c.snapshots, campaign: c.campaign, allMaps: c.allMaps };
  S.version = c.version; if (c.now) S.clockSkew = Date.now() / 1000 - c.now;
  document.title = S.map.name + ' · ShadowGrid';
  $('map-name').value = S.map.name;
  if (c.campaign) { $('back-link').href = `/game/${c.campaign.id}#maps`; $('back-link').textContent = '‹ ' + c.campaign.name; }
  $('paint-color').value = colors().cellDefault; $('paint-border').value = colors().cellBorder;
  $('door-color').value = S.map.settings.doorPalette[0] || colors().doorDefault;
  $('marker-color').value = colors().markerDefault;
  $('legend-toggle').checked = S.map.settings.legendVisible !== false;
  $('rooms-toggle').checked = S.map.settings.showRoomLabels !== false;
  renderPaintSwatches(); renderDoorSwatches(); renderMarkerTypes(); renderLinkMaps(); renderRoomList(); renderSnapshots();
  $('link-id').value = newLinkId();
  if (c.rolls) renderRolls(c.rolls);
  const q = new URLSearchParams(location.search);
  if (q.get('view')) { setMode('play'); setViewAs(q.get('view')); S.follow = q.get('follow') === '1'; $('follow-player').checked = S.follow; history.replaceState(null, '', location.pathname); }
  else if (q.get('play')) { setMode('play'); history.replaceState(null, '', location.pathname); }
  else setMode('edit');
  vp.fit(); invalidate();
}
new ResizeObserver(() => requestDraw()).observe(wrap);
window.addEventListener('beforeunload', e => { flushFog(); if (S.dirty) { e.preventDefault(); e.returnValue = ''; } });
boot().catch(e => { if (e.message !== 'auth') toast('Could not load the map: ' + e.message); });
})();
