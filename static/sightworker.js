/* Line of sight off the main thread: the page sends the map once per version, then asks for sight fields;
   big maps and hexes no longer stall drawing or dragging. */
'use strict';
self.importScripts(new URL('sightcore.js' + (self.location.search || ''), self.location.href).href);
let current = { sig: null, map: null, world: null };

self.onmessage = ev => {
  const m = ev.data || {};
  if (m.type === 'map') {
    current = { sig: m.sig, map: m.map, world: null };
    return;
  }
  if (m.type === 'field') {
    if (m.sig !== current.sig || !current.map) { self.postMessage({ id: m.id, error: 'stale' }); return; }
    if (!current.world) current.world = self.SightCore.world(current.map);
    const f = self.SightCore.field(current.world, m.from, m.radius, m.opts || {});
    self.postMessage({ id: m.id, sig: m.sig, key: m.key, field: {
      from: f.from, radius: f.radius, seen: [...f.seen], hidden: [...f.hidden], dark: [...f.dark], far: [...f.far], blind: [...f.blind] } });
  }
};
