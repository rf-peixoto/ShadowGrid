/* GM view of one player's character sheet: every edit is free; approval controls on top. */
(async () => {
  const pid = document.body.dataset.playerId;
  let rev = null;
  const ui = Sheet.mount(document.getElementById('sheet-root'), {
    gm: true, sheetUrl: `/api/players/${pid}/sheet`, actionUrl: `/api/players/${pid}/sheet/action`,
    onSheet: sh => { rev = sh.player.charRev; document.getElementById('who').textContent = `${sh.player.name} · @${sh.player.username}`; document.title = `${sh.player.name} · ShadowGrid`; },
  });
  try { await SR.catalog(); await ui.load(); } catch (e) { if (e.message !== 'auth') toast(e.message); }
  // pick up the player's own changes while the GM has the sheet open
  const check = async () => {
    if (document.hidden || ui.editing() || document.querySelector('dialog[open]')) return;
    try { const sh = await api(`/api/players/${pid}/sheet`); if (sh.player.charRev !== rev || sh.player.status !== ui.get().player.status) ui.setSheet(sh); } catch { /* transient */ }
  };
  setInterval(check, 20000);
  Live.on(check);
})();
