/* Map-screen layout shared by the player app and the GM editor:
   a tabbed drawer on the left (collapsible), the combat strip on top of the map and a dice dock at the bottom.
   Remembers the open tab and what is collapsed per page. "[" toggles the drawer, "]" the dock. */
window.Layout = (() => {
  'use strict';
  let root = null, key = 'sg.layout', state = { pane: null, drawer: true, dock: true };
  const load = () => { try { Object.assign(state, JSON.parse(localStorage.getItem(key) || '{}')); } catch { /* ignore */ } };
  const save = () => { try { localStorage.setItem(key, JSON.stringify(state)); } catch { /* ignore */ } };
  const relayout = () => requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));

  function apply() {
    root.classList.toggle('drawer-collapsed', !state.drawer);
    root.classList.toggle('dock-collapsed', !state.dock);
    const tabs = [...root.querySelectorAll('[data-pane-btn]')].filter(b => !b.hidden && !b.closest('[hidden]'));
    if (tabs.length && !tabs.some(b => b.dataset.paneBtn === state.pane)) state.pane = tabs[0].dataset.paneBtn;
    root.querySelectorAll('[data-pane-btn]').forEach(b => { const on = b.dataset.paneBtn === state.pane; b.classList.toggle('active', on); b.setAttribute('aria-selected', on); });
    root.querySelectorAll('[data-pane]').forEach(p => p.classList.toggle('shown', p.dataset.pane === state.pane));
    const db = root.querySelector('.drawer-toggle');
    if (db) { db.textContent = state.drawer ? '‹' : '›'; db.title = state.drawer ? 'Hide the side panel ( [ )' : 'Show the side panel ( [ )'; }
    const kb = root.querySelector('.dock-toggle');
    if (kb) { kb.textContent = state.dock ? '▾' : '▴'; kb.title = state.dock ? 'Collapse the dice panel ( ] )' : 'Open the dice panel ( ] )'; }
  }
  function init(el, pageKey) {
    root = el; key = 'sg.layout.' + pageKey;
    load();
    root.querySelectorAll('[data-pane-btn]').forEach(b => b.addEventListener('click', () => show(b.dataset.paneBtn)));
    const db = root.querySelector('.drawer-toggle'); if (db) db.addEventListener('click', toggleDrawer);
    const kb = root.querySelector('.dock-toggle'); if (kb) kb.addEventListener('click', toggleDock);
    const dh = root.querySelector('.dock-head'); if (dh) dh.addEventListener('dblclick', toggleDock);
    document.addEventListener('keydown', e => {
      if (e.ctrlKey || e.metaKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable) return;
      if (e.key === '[') { toggleDrawer(); e.preventDefault(); }
      else if (e.key === ']') { toggleDock(); e.preventDefault(); }
    });
    apply(); relayout();
  }
  function show(pane, { open = true } = {}) {
    state.pane = pane;
    if (open) state.drawer = true;
    save(); apply(); relayout();
  }
  function toggleDrawer() { state.drawer = !state.drawer; save(); apply(); relayout(); }
  function toggleDock() { state.dock = !state.dock; save(); apply(); relayout(); }
  function openDock() { if (!state.dock) { state.dock = true; save(); apply(); relayout(); } }
  return { init, show, refresh: () => { if (root) apply(); }, current: () => state.pane, openDock, relayout };
})();
