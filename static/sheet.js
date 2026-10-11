/* Character sheet: used by the player app (/api/me/sheet) and the GM (/api/players/<id>/sheet). */
window.Sheet = (() => {
'use strict';
const SECTIONS = [
  ['overview', 'Overview'], ['attributes', 'Attributes'], ['skills', 'Skills'], ['qualities', 'Qualities'],
  ['magic', 'Magic & Resonance'], ['gear', 'Gear'], ['combat', 'Combat'], ['contacts', 'Contacts'], ['background', 'Background & notes'],
];

function mount(root, cfg) {
  /* cfg: { gm: bool, sheetUrl, actionUrl, post(path, body) (player only), onSheet(sheet), openStore(category), log: () => rolls } */
  const S = { sheet: null, section: localStorage.getItem('sg.section') || 'overview', busy: false };
  let CAT = SR.CAT;
  const shell = h('div.sheet');
  const nav = h('nav.subnav', { 'aria-label': 'Sheet sections' });
  const main = h('div.sheet-main');
  shell.append(nav, main);
  root.append(shell);
  let rollerEl = null;

  // ------------------------------------------------------------ data
  async function load() {
    CAT = await SR.catalog();
    set(await api(cfg.sheetUrl));
  }
  function set(sh, { rerender = true } = {}) {
    S.sheet = sh;
    if (cfg.onSheet) cfg.onSheet(sh);
    if (rerender) render();
  }
  async function act(action, params = {}, { quiet = false } = {}) {
    try {
      const sh = await api(cfg.actionUrl, 'POST', { action, ...params });
      set(sh);
      if (!quiet && sh.message && sh.message !== 'Saved.') toast(sh.message);
      return sh;
    } catch (e) { if (e.message !== 'auth') toast(e.message, 4000); render(); return null; }
  }
  const c = () => S.sheet.char, d = () => S.sheet.derived;
  const locked = () => S.sheet.locked;              // approved and not the GM
  const free = () => !S.sheet.locked;               // draft, or the GM

  // ------------------------------------------------------------ render with focus restore
  function render() {
    if (!S.sheet) return;
    const ae = document.activeElement, fk = ae && main.contains(ae) ? ae.dataset.k : null;
    const scroll = root.closest('.page') ? root.closest('.page').scrollTop : 0;
    nav.innerHTML = '';
    for (const [k, label] of SECTIONS) {
      if (k === 'magic' && c().magic_type === 'Mundane' && !c().spells.length && !c().powers.length && !c().foci.length) {
        nav.append(h('button' + (S.section === k ? '.active' : ''), { type: 'button', onclick: () => go(k), title: 'Mundane characters have no magic' }, label, h('span.hint', ' –')));
        continue;
      }
      nav.append(h('button' + (S.section === k ? '.active' : ''), { type: 'button', onclick: () => go(k) }, label));
    }
    main.innerHTML = '';
    main.append(header());
    const fn = { overview, attributes, skills, qualities, magic, gear, combat, contacts, background }[S.section] || overview;
    main.append(fn());
    if (fk) { const el = main.querySelector(`[data-k="${CSS.escape(fk)}"]`); if (el) el.focus(); }
    if (root.closest('.page')) root.closest('.page').scrollTop = scroll;
  }
  function go(k) { S.section = k; try { localStorage.setItem('sg.section', k); } catch { /* ignore */ } render(); }

  // ------------------------------------------------------------ header + approval banner
  function header() {
    const sh = S.sheet, p = sh.player, ch = c();
    const wrap = h('div');
    const st = sh.player.status;
    if (cfg.gm) {
      const b = h('div.banner' + (st === 'waiting' ? '.warn' : st === 'approved' ? '.ok' : ''));
      b.append(h('p', SR.statusTag(st), ' ',
        st === 'approved' ? 'Approved. The player now spends Karma for upgrades and purchases are final. You can still change anything.' :
        st === 'waiting' ? `${p.username} submitted this sheet. Review it, then approve it or send it back with a note.` :
        `${p.username} is still building this character.`));
      if (st !== 'approved') b.append(h('button.primary', { type: 'button', onclick: () => review('approve') }, 'Approve sheet'));
      if (st === 'waiting') b.append(h('button', { type: 'button', onclick: () => review('return') }, 'Send back…'));
      if (st === 'approved') b.append(h('button', { type: 'button', onclick: () => review('reopen') }, 'Reopen for free editing'));
      b.append(h('button', { type: 'button', onclick: gmOverride }, 'Set Karma / Nuyen / Edge…'));
      wrap.append(b);
    } else if (st !== 'approved') {
      const b = h('div.banner' + (st === 'waiting' ? '.info' : '.warn'));
      if (st === 'waiting') b.append(h('p', SR.statusTag(st), ' Your GM is reviewing this sheet. You can keep editing until it is approved.'),
        h('button', { type: 'button', onclick: () => submit(false) }, 'Withdraw'));
      else b.append(h('p', h('b', 'Character creation. '), 'Edit freely: everything you buy is refunded if you remove it. When you are done, send the sheet to your GM.',
        p.reviewNote ? h('span.warn', h('br'), 'GM note: ', p.reviewNote) : ''),
        h('button.primary', { type: 'button', onclick: () => submit(true) }, 'Submit for approval'));
      wrap.append(b);
    }
    const top = h('div.section-head',
      h('h2', ch.name || h('span.muted', 'Unnamed runner'), ' ', h('span.hint', [ch.metatype, ch.role, ch.magic_type !== 'Mundane' ? ch.magic_type : ''].filter(Boolean).join(' · '))),
      h('div.row.tight', SR.healthTag(d().status), h('span.chip', h('span.k', 'Karma'), h('b', ch.karma)), h('span.chip', h('span.k', 'Nuyen'), h('b', money(ch.nuyen))),
        h('span.chip', h('span.k', 'Edge'), SR.pips(ch.current_edge, d().edge_max), h('b', `${ch.current_edge}/${d().edge_max}`))));
    wrap.append(top);
    return wrap;
  }
  async function submit(yes) {
    try { set(await api('/api/me/submit', 'POST', { submit: yes })); toast(yes ? 'Sent to your GM for approval.' : 'Back to draft.'); } catch (e) { toast(e.message); }
  }
  async function review(decision) {
    let note = '';
    if (decision === 'return') { note = await UI.prompt('Send back to the player', 'What should they change?', { required: false, ok: 'Send back' }); if (note === null) return; }
    if (decision === 'approve' && !await UI.confirm('Approve this sheet? From now on the player spends Karma to improve and purchases are final. Edge is filled up.', { ok: 'Approve' })) return;
    try { set(await api(`/api/players/${S.sheet.player.id}/review`, 'POST', { decision, note })); toast(decision === 'approve' ? 'Sheet approved.' : 'Sheet sent back.'); } catch (e) { toast(e.message); }
  }
  async function gmOverride() {
    const ch = c();
    const k = h('input', { type: 'number', value: ch.karma }), n = h('input', { type: 'number', value: ch.nuyen }), e = h('input', { type: 'number', min: 0, max: 7, value: ch.current_edge });
    const ok = await UI.modal('GM override', h('div', h('p.hint', 'Sets exact values. Changes to Karma and Nuyen are recorded in the history. For awards to several players use the game page.'),
      h('div.form-grid', h('label', 'Karma', k), h('label', 'Nuyen', n), h('label', 'Current Edge (0-7)', e))), { ok: 'Apply', narrow: true });
    if (ok) act('admin_set', { karma: +k.value, nuyen: +n.value, current_edge: +e.value });
  }

  // ------------------------------------------------------------ helpers
  const field = (label, el, hint) => h('label', label, el, hint ? h('small.hint', hint) : null);
  function infoInput(key, { type = 'text', lockedField = false, max } = {}) {
    const dis = lockedField && locked();
    return h('input', { type, value: c()[key] ?? '', 'data-k': 'info.' + key, disabled: dis, max, min: type === 'number' ? 0 : undefined,
      onchange: e => act('set_info', { [key]: type === 'number' ? +e.target.value : e.target.value }, { quiet: true }) });
  }
  function infoSelect(key, values, { lockedField = false, labels } = {}) {
    const dis = lockedField && locked();
    return h('select', { 'data-k': 'info.' + key, disabled: dis, onchange: e => act('set_info', { [key]: e.target.value }, { quiet: true }) },
      values.map(v => option(v, labels ? labels(v) : (v || 'None'), (c()[key] ?? '') === v)));
  }
  const lockNote = () => locked() ? h('p.hint', '🔒 Approved: metatype, role, magic type and initiation are set by the GM.') : null;

  // ------------------------------------------------------------ overview
  function overview() {
    const ch = c(), dv = d();
    const out = h('div');
    const portrait = h('div.portrait', ch.portrait ? { style: { backgroundImage: `url("${ch.portrait}")` } } : {}, ch.portrait ? '' : 'No portrait');
    const file = h('input', { type: 'file', accept: 'image/*', hidden: true, onchange: e => loadPortrait(e.target.files[0]) });
    const pcol = h('div.col', portrait, h('div.row.tight', file, h('button.small', { type: 'button', onclick: () => file.click() }, ch.portrait ? 'Change' : 'Upload'),
      ch.portrait ? h('button.small.ghost', { type: 'button', onclick: () => act('set_portrait', { data: null }) }, 'Remove') : null));
    const lifestyleCost = CAT.lifestyleCost[ch.lifestyle] || 0;
    const form = h('div.form-grid',
      field('Name', infoInput('name')),
      field('Metatype', infoSelect('metatype', CAT.metatypes, { lockedField: true })),
      field('Role', infoSelect('role', ['', ...Object.keys(CAT.roles)], { lockedField: true, labels: v => v ? `${v} (${Object.entries(CAT.roles[v]).map(([a, b]) => `+${b} ${a}`).join(', ')})` : 'None' })),
      field('Magic / Resonance', infoSelect('magic_type', CAT.magicTypes, { lockedField: true })),
      field('Tradition', infoSelect('tradition', ['', ...CAT.traditions.filter(t => t !== 'None')])),
      field('Mentor spirit', infoInput('mentor_spirit')),
      field('Initiation grade', infoInput('initiation_grade', { type: 'number', lockedField: true, max: 99 })),
      field('Lifestyle', infoSelect('lifestyle', CAT.lifestyles, { labels: v => `${v} (${money(CAT.lifestyleCost[v])}/mo)` })),
      field('Age', infoInput('age', { type: 'number', max: 999 })),
      field('Reputation', infoInput('reputation', { type: 'number', max: 99 })));
    out.append(h('div.card', h('div.overview-top', pcol, h('div', form, lockNote()))));

    const stats = h('div.stats',
      stat('Physical', `${Math.min(dv.physical_damage, dv.physical_boxes)}/${dv.physical_boxes}`),
      stat('Stun', `${dv.stun_damage}/${dv.stun_boxes}`),
      stat('Wound mod', dv.wound_modifier || '0'),
      stat('Initiative', `${dv.initiative_score} + ${dv.initiative_dice}d6`),
      stat('Defense rating', dv.defense_rating),
      stat('Armor', dv.armor_rating),
      stat('Weapon accuracy', dv.weapon_accuracy),
      stat('Essence', dv.attributes.Essence),
      ch.magic_type !== 'Mundane' && ch.magic_type !== 'Technomancer' ? stat('Magic', dv.attributes.Magic) : null,
      ch.magic_type === 'Technomancer' ? stat('Resonance', dv.attributes.Resonance) : null);
    out.append(h('div.card', h('h3', 'Quick stats', h('button.small', { type: 'button', onclick: () => go('combat') }, 'Combat ›')), stats));

    const econ = h('div.card', h('h3', 'Karma & Nuyen'),
      h('div.stats', stat('Karma', ch.karma), stat('Nuyen', money(ch.nuyen)), stat('Gear value', money(dv.gear_value)), stat('Lifestyle', `${money(lifestyleCost)}`, '/month')),
      cfg.gm ? null : h('div.row.mt',
        h('button', { type: 'button', onclick: tradeKarma, disabled: !ch.karma }, `Trade Karma for Nuyen (1 = ${money(CAT.rules.nuyenPerKarma)})`),
        h('button', { type: 'button', onclick: async () => { if (await UI.confirm(`Pay ${money(lifestyleCost)} for one month of ${ch.lifestyle} lifestyle?`, { ok: 'Pay' })) act('pay_lifestyle'); } }, 'Pay a month of lifestyle'),
        cfg.openStore ? h('button', { type: 'button', onclick: () => cfg.openStore() }, 'Open the store ›') : null),
      h('p.hint.mt', cfg.gm ? 'Changes you make here are free and are recorded in the history as GM changes.' :
        locked() ? 'Karma and Nuyen change through upgrades, purchases, runs and GM awards. Every change is listed below.' :
          'While creating the character, removing purchases refunds them in full.'));
    out.append(econ);
    out.append(history());
    return out;
  }
  function stat(k, v, small) { return h('div.stat', h('div.k', k), h('div.v', v, small ? h('small', small) : null)); }
  async function tradeKarma() {
    const v = await UI.prompt('Trade Karma for Nuyen', `How much Karma? (you have ${c().karma}, 1 Karma = ${money(CAT.rules.nuyenPerKarma)})`, { type: 'number', value: 1, min: 1, ok: 'Trade' });
    if (v) act('trade_karma', { amount: +v });
  }
  function loadPortrait(f) {
    if (!f) return;
    const img = new Image(), url = URL.createObjectURL(f);
    img.onload = () => {
      const s = Math.min(1, 400 / Math.max(img.width, img.height));
      const cv = h('canvas', { width: Math.round(img.width * s), height: Math.round(img.height * s) });
      cv.getContext('2d').drawImage(img, 0, 0, cv.width, cv.height);
      URL.revokeObjectURL(url);
      act('set_portrait', { data: cv.toDataURL('image/jpeg', 0.85) });
    };
    img.onerror = () => toast('That file is not an image.');
    img.src = url;
  }
  function history() {
    const rows = S.sheet.ledger;
    const t = h('table.list', h('thead', h('tr', h('th', 'When'), h('th', 'What'), h('th.right', 'Change'), h('th.right', 'Balance'))));
    const tb = h('tbody');
    for (const r of rows) {
      const val = r.kind === 'karma' ? `${r.delta > 0 ? '+' : ''}${r.delta} Karma` : `${r.delta > 0 ? '+' : '−'}${money(Math.abs(r.delta))}`;
      tb.append(h('tr', h('td.nowrap.hint', timeAgo(r.at)), h('td', r.reason, r.byGm ? h('span.hint', ' (GM)') : ''),
        h('td.right.nowrap', { class: r.delta > 0 ? 'good' : 'bad' }, val), h('td.right.nowrap.hint', r.kind === 'karma' ? r.balance : money(r.balance))));
    }
    t.append(tb);
    return h('div.card', h('h3', 'History'), rows.length ? h('div.table-wrap', t) : h('p.hint', 'Nothing yet. Purchases, upgrades, run rewards and GM awards appear here.'));
  }

  // ------------------------------------------------------------ attributes
  function attributes() {
    const ch = c(), dv = d(), mins = CAT.metatypeMin[ch.metatype] || {};
    const t = h('table.list', h('thead', h('tr', h('th', 'Attribute'), h('th', 'Base'), h('th', 'Modifiers'), h('th', 'Rating'), h('th', ''))));
    const tb = h('tbody');
    for (const a of CAT.attributes) {
      const base = ch.base_attributes[a];
      const bonuses = (dv.bonuses[a] || []).map(([src, v]) => h('div.bonus' + (v < 0 ? '.neg' : ''), `${v > 0 ? '+' : ''}${v} ${src}`));
      if (mins[a] && base < mins[a]) bonuses.unshift(h('div.bonus', `min ${mins[a]} (${ch.metatype})`));
      let baseCell, act2 = null;
      if (a === 'Essence') baseCell = h('span', base);
      else if (free()) baseCell = h('input', { type: 'number', min: ['Magic', 'Resonance'].includes(a) ? 0 : 1, max: CAT.rules.attrMax, value: base, 'data-k': 'attr.' + a,
        onchange: e => act('set_attribute', { attr: a, value: +e.target.value }, { quiet: true }) });
      else baseCell = h('span', base);
      if (a !== 'Essence' && !cfg.gm) {
        const eff = Math.max(base, mins[a] || 0), cost = (eff + 1) * CAT.rules.karmaPerRating;
        if (locked() && eff < CAT.rules.attrMax) act2 = h('button.small', { type: 'button', disabled: ch.karma < cost,
          title: ch.karma < cost ? `Needs ${cost} Karma` : '', onclick: async () => { if (await UI.confirm(`Raise ${a} to ${eff + 1} for ${cost} Karma?`, { ok: 'Raise' })) act('raise_attribute', { attr: a }); } },
          `Raise · ${cost} K`);
      }
      const dim = (a === 'Magic' && ['Mundane', 'Technomancer'].includes(ch.magic_type)) || (a === 'Resonance' && ch.magic_type !== 'Technomancer');
      tb.append(h('tr' + (dim ? '.dim' : ''), h('td', a), h('td', baseCell), h('td', bonuses), h('td.attr-total', dv.attributes[a]), h('td.right', act2)));
    }
    t.append(tb);
    const head = h('div.row.between', h('p.hint.mb0', free() ? (cfg.gm ? 'As GM you can set any base value.' : 'Set base ratings freely while creating your character. Metatype minimums, your role and gear are applied automatically.')
      : `Raising an attribute costs the new rating × ${CAT.rules.karmaPerRating} Karma.`),
      free() && !cfg.gm ? h('button', { type: 'button', onclick: async () => { if (await UI.confirm('Roll 1d6 for every physical and mental attribute (and Edge)? This replaces the current base values.', { ok: 'Roll' })) act('autoroll'); } }, 'Auto roll attributes') : null);
    return h('div.card', head, h('div.table-wrap.mt', t));
  }

  // ------------------------------------------------------------ skills
  function skills() {
    const ch = c(), pools = Object.fromEntries(S.sheet.pools.map(p => [p.key, p]));
    const t = h('table.list', h('thead', h('tr', h('th', 'Skill'), h('th', 'Linked'), h('th', 'Rank'), h('th', 'Specialization (+2 dice)'), h('th.right', 'Pool'))));
    const tb = h('tbody');
    for (const s of CAT.skills) {
      const rank = ch.skills[s] || 0, spec = ch.specializations[s] || '';
      let rankCell;
      if (free()) rankCell = h('input', { type: 'number', min: 0, max: CAT.rules.skillMax, value: rank, 'data-k': 'skill.' + s,
        onchange: e => act('set_skill', { skill: s, rank: +e.target.value }, { quiet: true }) });
      else {
        const cost = (rank + 1) * CAT.rules.karmaPerRating;
        rankCell = h('span.row.tight', h('b', rank), rank < CAT.rules.skillMax ? h('button.small', { type: 'button', disabled: ch.karma < cost,
          onclick: async () => { if (await UI.confirm(`${rank ? 'Raise' : 'Learn'} ${s} to ${rank + 1} for ${cost} Karma?`, { ok: 'Confirm' })) act('set_skill', { skill: s, rank: rank + 1 }); } }, `${rank ? 'Raise' : 'Learn'} · ${cost} K`) : null);
      }
      const specs = CAT.specializations[s] || [];
      const specSel = h('select', { 'data-k': 'spec.' + s, disabled: !rank || (locked() && spec),
        title: locked() && !spec ? `Costs ${CAT.rules.karmaSpec} Karma` : '',
        onchange: async e => {
          const v = e.target.value;
          if (locked() && v && !await UI.confirm(`Specialize in ${v} for ${CAT.rules.karmaSpec} Karma?`, { ok: 'Confirm' })) { render(); return; }
          act('set_skill', { skill: s, spec: v }, { quiet: !locked() });
        } }, option('', rank ? 'None' : '—'), specs.map(x => option(x, x, x === spec)));
      const pool = pools['spec:' + s] || pools['skill:' + s];
      tb.append(h('tr' + (rank ? '' : '.dim'), h('td', s), h('td.hint', CAT.skillAttribute[s]), h('td', rankCell), h('td', specSel),
        h('td.right', h('b', { title: SR.breakdown(pool.parts) }, pool.value))));
    }
    t.append(tb);
    return h('div.card', h('p.hint', free() ? 'Pools add the linked attribute. Untrained skills roll the attribute −1.' :
      `Raising a skill costs the new rank × ${CAT.rules.karmaPerRating} Karma; a specialization costs ${CAT.rules.karmaSpec} Karma.`), h('div.table-wrap', t));
  }

  // ------------------------------------------------------------ qualities
  function qualities() {
    const ch = c(), out = h('div');
    const eff = q => { const e = CAT.qualityEffects[q] || {}; return Object.entries(e).filter(([k]) => k !== 'karma').map(([k, v]) => `${v > 0 ? '+' : ''}${v} ${k}`).join(', '); };
    const cur = h('div.card', h('h3', 'Your qualities'));
    if (!ch.qualities.length) cur.append(h('p.hint', 'None yet.'));
    const list = h('div.pick-list');
    for (const q of ch.qualities) {
      const pos = CAT.qualities.Positive.includes(q), k = (CAT.qualityEffects[q] || {}).karma || 0;
      list.append(h('div.pick.have', h('div', h('div', (pos ? '＋ ' : '－ ') + q), h('div.meta', eff(q) || 'No numeric effect')),
        free() ? h('button.small.danger', { type: 'button', title: cfg.gm ? '' : pos ? `Refunds ${k} Karma` : `Costs ${-k} Karma to remove`, onclick: () => act('remove_quality', { quality: q }) }, 'Remove') : null));
    }
    cur.append(list);
    if (locked()) cur.append(h('p.hint.mt', '🔒 Your sheet is approved: ask the GM to add or remove qualities.'));
    out.append(cur);
    if (free()) {
      for (const side of ['Positive', 'Negative']) {
        const card = h('div.card', h('h3', `${side} qualities`, h('span.hint', side === 'Positive' ? 'cost Karma' : 'give Karma')));
        const pl = h('div.pick-list');
        for (const q of CAT.qualities[side]) {
          if (ch.qualities.includes(q)) continue;
          const k = Math.abs((CAT.qualityEffects[q] || {}).karma || 0);
          pl.append(h('div.pick', h('div', h('div', q), h('div.meta', [eff(q), `${k} Karma`].filter(Boolean).join(' · '))),
            h('button.small', { type: 'button', disabled: side === 'Positive' && !cfg.gm && ch.karma < k, onclick: () => act('add_quality', { quality: q }) }, 'Add')));
        }
        card.append(pl); out.append(card);
      }
    }
    return out;
  }

  // ------------------------------------------------------------ magic
  function magic() {
    const ch = c(), dv = d(), out = h('div');
    if (ch.magic_type === 'Mundane') out.append(h('div.banner.info', h('p', 'This character is Mundane. Pick a magic type on the Overview to use spells, powers and foci.')));
    // spells
    const sp = h('div.card', h('h3', 'Spells', h('span.row.tight',
      h('button.small', { type: 'button', onclick: () => pickPredef('Spell') }, 'Learn a spell'),
      h('button.small.ghost', { type: 'button', onclick: () => customMagic('Spell') }, 'Custom…'))));
    if (locked()) sp.append(h('p.hint', `Learning a new spell costs ${CAT.rules.karmaSpell} Karma.`));
    sp.append(magicTable(ch.spells, ['Type', 'Drain'], 'Spell', 'remove_spell', 'save_spell'));
    out.append(sp);
    // powers
    const over = dv.power_points_used > dv.power_points_available;
    const pw = h('div.card', h('h3', h('span', 'Adept powers ', h('span.chip', { class: over ? 'bad' : '' }, `Power Points ${dv.power_points_used} / ${dv.power_points_available}`)),
      h('span.row.tight', h('button.small', { type: 'button', onclick: () => pickPredef('Power') }, 'Add a power'),
        h('button.small.ghost', { type: 'button', onclick: () => customMagic('Power') }, 'Custom…'))));
    if (!['Adept', 'Mystic Adept'].includes(ch.magic_type)) pw.append(h('p.hint', 'Power Points come from Magic for Adepts and Mystic Adepts.'));
    pw.append(magicTable(ch.powers, ['Activation', 'Effect', 'Cost'], 'Power', 'remove_power', 'save_power'));
    out.append(pw);
    // foci
    const fo = h('div.card', h('h3', 'Foci', h('span.row.tight', h('button.small', { type: 'button', onclick: () => pickPredef('Focus') }, 'Add a focus'),
      h('button.small.ghost', { type: 'button', onclick: () => customMagic('Focus') }, 'Custom…'))));
    fo.append(h('p.hint', 'Bonding costs Force × type multiplier in Karma. A bonded Power Focus adds its Force to Magic.'));
    const t = h('table.list', h('thead', h('tr', h('th', 'Focus'), h('th', 'Type'), h('th', 'Force'), h('th', 'Bond cost'), h('th', ''))));
    const tb = h('tbody');
    ch.foci.forEach((f, i) => {
      const bonded = String(f.Bonded).toLowerCase() === 'yes';
      const cost = (+f.Force || 0) * (CAT.focusBond[f.Type] || 1);
      tb.append(h('tr', h('td', h('a', { href: '#', onclick: e => { e.preventDefault(); showItem(f); } }, f.name), f._custom ? h('span.tag.custom', ' custom') : ''), h('td', f.Type), h('td', f.Force), h('td', `${cost} K`),
        h('td.right.nowrap', h('button.small' + (bonded ? '.good' : ''), { type: 'button', disabled: bonded && locked(), onclick: () => act('bond_focus', { index: i }) }, bonded ? '✓ Bonded' : `Bond (${cost} K)`), ' ',
          free() ? h('button.small.ghost', { type: 'button', onclick: async () => { const it = await SR.editItem('Focus', f); if (it) act('save_focus', { edit: i, item: it }); } }, 'Edit') : null,
          free() ? h('button.small.danger', { type: 'button', onclick: () => act('remove_focus', { index: i }) }, '✕') : null)));
    });
    t.append(tb);
    fo.append(ch.foci.length ? h('div.table-wrap', t) : h('p.hint', 'No foci.'));
    out.append(fo);
    return out;
  }
  function magicTable(list, cols, kind, removeAction, saveAction) {
    if (!list.length) return h('p.hint', 'None yet.');
    const t = h('table.list', h('thead', h('tr', h('th', 'Name'), cols.map(x => h('th', x)), h('th', ''))));
    const tb = h('tbody');
    list.forEach((it, i) => {
      const canRemove = free();
      const canEdit = free();
      tb.append(h('tr', h('td', h('a', { href: '#', onclick: e => { e.preventDefault(); showItem(it); } }, it.name), it._custom ? h('span.tag.custom', ' custom') : ''),
        cols.map(x => h('td', it[x] ?? '')),
        h('td.right.nowrap', canEdit ? h('button.small.ghost', { type: 'button', onclick: async () => { const n = await SR.editItem(kind, it); if (n) act(saveAction, { edit: i, item: n }); } }, 'Edit') : null,
          canRemove ? h('button.small.danger', { type: 'button', onclick: () => act(removeAction, { index: i }) }, '✕') : null)));
    });
    t.append(tb);
    return h('div.table-wrap', t);
  }
  async function pickPredef(kind) {
    const src = { Spell: CAT.spells, Power: CAT.powers, Focus: CAT.foci }[kind];
    const action = { Spell: 'save_spell', Power: 'save_power', Focus: 'save_focus' }[kind];
    const have = new Set((kind === 'Spell' ? c().spells : kind === 'Power' ? c().powers : c().foci).map(x => x.name));
    let chosen = null;
    const search = h('input', { type: 'search', placeholder: 'Search…', oninput: () => draw() });
    const list = h('div.pick-list', { style: { maxHeight: '55vh', overflowY: 'auto' } });
    function draw() {
      list.innerHTML = '';
      const q = search.value.toLowerCase();
      src.forEach((it, i) => {
        if (q && !(it.name + ' ' + (it.description || '')).toLowerCase().includes(q)) return;
        const meta = kind === 'Spell' ? `${it.Type} · Drain ${it.Drain}` : kind === 'Power' ? `${it.Cost} PP · ${it.Effect || ''}` : `${it.Type} · Force ${it.Force}`;
        list.append(h('label.pick' + (have.has(it.name) ? '.have' : ''), { title: it.description || '' }, h('div', h('div', it.name), h('div.meta', meta)),
          h('input', { type: 'radio', name: 'pd', onchange: () => { chosen = i; } })));
      });
    }
    draw();
    const cost = kind === 'Spell' && locked() ? ` (${CAT.rules.karmaSpell} Karma)` : '';
    const ok = await UI.modal(kind === 'Spell' ? 'Learn a spell' : kind === 'Power' ? 'Add an adept power' : 'Add a focus', h('div', search, h('div.mt', list)), { ok: `Add${cost}`, wide: true });
    if (ok && chosen !== null) act(action, { index: chosen });
  }
  async function customMagic(kind) {
    const it = await SR.editItem(kind, {}, { title: `Custom ${kind.toLowerCase()}` });
    if (it) act({ Spell: 'save_spell', Power: 'save_power', Focus: 'save_focus' }[kind], { item: it });
  }
  function showItem(it) {
    UI.info(it.name, h('div', it.description ? h('p', it.description) : null, SR.itemDetails(it, ['Bonded', 'Equipped']),
      it.Price !== undefined ? h('p.mt', 'Price: ', h('b', money(it.Price))) : null));
  }

  // ------------------------------------------------------------ gear (inventory)
  function gear() {
    const ch = c(), dv = d(), out = h('div');
    out.append(h('div.card', h('div.stats', stat('Armor rating', dv.armor_rating), stat('Weapon accuracy', dv.weapon_accuracy),
      stat('Essence', dv.attributes.Essence), stat('Gear value', money(dv.gear_value)), stat('Nuyen', money(ch.nuyen))),
      h('div.row.mt', cfg.openStore ? h('button.primary', { type: 'button', onclick: () => cfg.openStore() }, 'Buy gear in the store ›') : null,
        cfg.gm ? h('button', { type: 'button', onclick: gmGive }, 'Give an item…') : null,
        h('span.hint', free() ? (cfg.gm ? 'GM changes are free.' : 'Removing an item refunds its price while you are creating the character.') : 'Purchases are final; removing an item discards it.'))));
    let any = false;
    for (const cat of CAT.gearCategories) {
      const items = ch.gear[cat] || [];
      if (!items.length) continue;
      any = true;
      const equippable = CAT.equippable.includes(cat);
      const t = h('table.list', h('thead', h('tr', h('th', 'Item'), h('th', 'Details'), h('th.right', 'Price'), h('th', ''))));
      const tb = h('tbody');
      items.forEach((it, i) => {
        const on = String(it.Equipped ?? 'Yes').toLowerCase() !== 'no';
        const det = Object.entries(it).filter(([k, v]) => !['name', 'description', 'Price', 'Equipped', '_custom', 'Type'].includes(k) && v !== '-' && v !== '').map(([k, v]) => `${k} ${v}`).join(' · ');
        tb.append(h('tr' + (equippable && !on ? '.dim' : ''),
          h('td', h('a', { href: '#', onclick: e => { e.preventDefault(); showItem(it); } }, it.name), it._custom ? h('span.tag.custom', ' custom') : '', it.Type ? h('div.hint', it.Type) : null),
          h('td.hint', det),
          h('td.right.nowrap', money(it.Price || 0)),
          h('td.right.nowrap',
            equippable ? h('button.small' + (on ? '.good' : ''), { type: 'button', onclick: () => act('toggle_equipped', { category: cat, index: i }, { quiet: true }), title: on ? 'Equipped: click to store' : 'Stored: click to equip' }, on ? '✓ Equipped' : 'Equip') : null,
            cat === 'Medkits' ? h('button.small', { type: 'button', onclick: () => act('use_medkit', { index: i }) }, 'Use') : null, ' ',
            h('button.small.ghost', { type: 'button', onclick: async () => { const n = await SR.editItem(cat, it, { lockedFields: locked() }); if (n) act('edit_item', { category: cat, index: i, item: n }); } }, 'Edit'),
            h('button.small.danger', { type: 'button', title: free() && !cfg.gm ? `Refund ${money(it.Price || 0)}` : 'Discard', onclick: async () => {
              if (locked() && !await UI.confirm(`Discard ${it.name}? You won't get the ${money(it.Price || 0)} back.`, { ok: 'Discard', danger: true })) return;
              act('remove_item', { category: cat, index: i });
            } }, free() && !cfg.gm ? 'Return' : '✕'))));
      });
      t.append(tb);
      out.append(h('div.card', h('h3', cat, h('span.hint', `${items.length} item${items.length > 1 ? 's' : ''}`)), h('div.table-wrap', t)));
    }
    if (!any) out.append(h('div.card.empty', h('h3', 'No gear yet'), h('p', 'Weapons, armor, cyberware and everything else is bought in the store.')));
    return out;
  }
  /* GM: give an item for free, picked from the store presets or filled in by hand. */
  async function gmGive() {
    let cat = CAT.gearCategories[0], chosen = 'custom';
    const cats = h('div.cat-chips');
    const search = h('input', { type: 'search', placeholder: 'Search this category…', oninput: () => draw() });
    const tweak = h('input', { type: 'checkbox' });
    const list = h('div.pick-list', { style: { maxHeight: '48vh', overflowY: 'auto' } });
    function draw() {
      cats.innerHTML = '';
      for (const c of CAT.gearCategories) cats.append(h('button.small' + (c === cat ? '.active' : ''), { type: 'button', onclick: () => { cat = c; chosen = 'custom'; draw(); } }, c));
      list.innerHTML = '';
      list.append(h('label.pick', h('div', h('div', h('b', 'Custom item…')), h('div.meta', 'Fill in every field yourself')),
        h('input', { type: 'radio', name: 'give', checked: chosen === 'custom', onchange: () => { chosen = 'custom'; } })));
      const q = search.value.trim().toLowerCase();
      CAT.gear[cat].forEach((it, i) => {
        if (q && !JSON.stringify(it).toLowerCase().includes(q)) return;
        const meta = Object.entries(it).filter(([k, v]) => !['name', 'Price', 'description'].includes(k) && v !== '-').slice(0, 4).map(([k, v]) => `${k} ${v}`).join(' · ');
        list.append(h('label.pick', h('div', h('div', it.name), h('div.meta', `${money(it.Price)} · ${meta}`)),
          h('input', { type: 'radio', name: 'give', checked: chosen === i, onchange: () => { chosen = i; } })));
      });
    }
    draw();
    const ok = await UI.modal('Give an item', h('div',
      h('p.hint', `Free for ${S.sheet.player.name}: no nuyen is taken. Pick a preset from the store list, or make a custom item.`),
      cats, h('div.mt', search), h('div.mt', list),
      h('label.check.mt', tweak, 'Let me edit the preset before giving it')), { ok: 'Give', wide: true });
    if (!ok) return;
    if (chosen === 'custom' || tweak.checked) {
      const base = chosen === 'custom' ? {} : CAT.gear[cat][chosen];
      const it = await SR.editItem(cat, base, { title: chosen === 'custom' ? `Custom ${cat}` : `Give ${base.name}`, ok: 'Give' });
      if (it) act('buy', { category: cat, item: it, free: true });
    } else act('buy', { category: cat, index: chosen, free: true });
  }

  // ------------------------------------------------------------ combat
  function combat() {
    const ch = c(), dv = d(), out = h('div');
    const cm = { p: dv.physical_damage, pm: dv.physical_boxes, s: dv.stun_damage, sm: dv.stun_boxes, ov: dv.overflow_boxes };
    const setDmg = (track, value) => act('set_damage', { track, value }, { quiet: true });
    const mon = h('div.card', h('h3', 'Condition monitors', h('span.row.tight', SR.healthTag(dv.status), dv.wound_modifier ? h('span.tag.status-Wounded', `Wounds ${dv.wound_modifier} dice`) : null)),
      h('div.grid2', SR.monitor('physical', cm, { onSet: setDmg }), SR.monitor('stun', cm, { onSet: setDmg })),
      h('p.hint.mt', 'Click a box to fill up to it. Every 3 boxes is −1 die. Stun beyond the track overflows into Physical; Physical beyond the track uses overflow boxes (Body); past those the character is dead.'),
      h('div.row', h('button', { type: 'button', onclick: () => act('rest') }, 'Rest (heal 1 Stun)'),
        (ch.gear.Medkits || []).length ? h('button', { type: 'button', onclick: () => act('use_medkit', { index: 0 }) }, `Use ${ch.gear.Medkits[0].name}`) : null));
    out.append(mon);
    const edgeCard = h('div.card', h('h3', 'Edge', h('span.row.tight', SR.pips(ch.current_edge, dv.edge_max), h('b', `${ch.current_edge} / ${dv.edge_max}`))),
      h('p.hint', cfg.gm ? 'Refresh or award Edge from the game page, or set it with “Set Karma / Nuyen / Edge”.' :
        'Your GM refreshes and awards Edge (max 7). Spend it on a roll (after rolling) or here:'),
      !cfg.gm ? h('button', { type: 'button', disabled: !ch.current_edge, onclick: () => SR.edgeMenu(S.sheet, cfg.post, () => reload()) }, 'Spend Edge…') : null);
    const st = h('div.card', h('h3', 'Derived'), h('div.stats', stat('Initiative', `${dv.initiative_score} + ${dv.initiative_dice}d6`), stat('Defense rating', dv.defense_rating),
      stat('Armor', dv.armor_rating), stat('Accuracy', dv.weapon_accuracy), stat('Wound mod', dv.wound_modifier || 0)));
    out.append(h('div.grid2', edgeCard, st));
    if (!cfg.gm && cfg.post) {
      if (!rollerEl) rollerEl = SR.roller({ getSheet: () => S.sheet, post: cfg.post, onRolled: res => { if (res.me) mergeMe(res.me); cfg.onRolled && cfg.onRolled(res); } });
      const logEl = h('div.log', { style: { maxHeight: '420px' } });
      out.append(h('div.grid2', h('div.card', h('h3', 'Dice roller'), rollerEl), h('div.card', h('h3', 'Table log'), logEl)));
      rollerEl.render();
      if (cfg.log) SR.renderLog(logEl, cfg.log());
      S.logEl = logEl;
    }
    return out;
  }
  function mergeMe(me) {
    if (!S.sheet) return;
    S.sheet.char.current_edge = me.edge.cur;
    S.sheet.player = Object.assign(S.sheet.player, me);
    if (cfg.onSheet) cfg.onSheet(S.sheet);
  }

  // ------------------------------------------------------------ contacts
  function contacts() {
    const ch = c();
    const card = h('div.card', h('h3', 'Contacts', h('button.small', { type: 'button', onclick: () => editContact(null) }, 'Add contact')));
    if (!ch.contacts.length) { card.append(h('p.hint', 'Fixers, Johnsons, street docs… add the people your runner can call.')); return card; }
    const t = h('table.list', h('thead', h('tr', h('th', 'Name'), h('th', 'Type'), h('th', 'Loyalty'), h('th', 'Connection'), h('th', ''))));
    const tb = h('tbody');
    ch.contacts.forEach((ct, i) => tb.append(h('tr.clickable', { onclick: e => { if (!e.target.closest('button')) editContact(i); }, title: ct.notes || '' },
      h('td', h('b', ct.name)), h('td', ct.type), h('td', ct.loyalty), h('td', ct.connection),
      h('td.right', h('button.small.danger', { type: 'button', onclick: async () => { if (await UI.confirm(`Remove ${ct.name}?`, { danger: true, ok: 'Remove' })) act('remove_contact', { index: i }); } }, '✕')))));
    t.append(tb);
    card.append(h('div.table-wrap', t));
    return card;
  }
  async function editContact(i) {
    const ct = i === null ? {} : c().contacts[i];
    const name = h('input', { value: ct.name || '', required: true });
    const type = h('input', { value: ct.type || '', list: 'contact-types' });
    const loyalty = h('select', CAT.loyalty.map(l => option(l, l, ct.loyalty === l)));
    const conn = h('input', { value: ct.connection || '' });
    const notes = h('textarea', { rows: 4 }, ct.notes || '');
    const dl = h('datalist#contact-types', CAT.contactTypes.map(x => option(x)));
    const ok = await UI.modal(i === null ? 'New contact' : `Edit ${ct.name}`, h('div', dl, h('div.form-grid', h('label', 'Name', name), h('label', 'Type', type), h('label', 'Loyalty', loyalty), h('label', 'Connection', conn)), h('label.stack', 'Notes', notes)));
    if (ok) act('save_contact', { index: i, contact: { name: name.value, type: type.value, loyalty: loyalty.value, connection: conn.value, notes: notes.value } });
  }

  // ------------------------------------------------------------ background
  function background() {
    const ch = c();
    const bg = h('textarea', { rows: 14, 'data-k': 'info.background', placeholder: 'Where your runner comes from, what they want, who they owe…', onchange: e => act('set_info', { background: e.target.value }, { quiet: true }) }, ch.background || '');
    const notes = h('textarea', { rows: 8, 'data-k': 'info.notes', placeholder: 'Session notes, leads, names to remember…', onchange: e => act('set_info', { notes: e.target.value }, { quiet: true }) }, ch.notes || '');
    return h('div', h('div.card', h('h3', 'Background'), bg, h('p.hint', 'Saved when you click outside the box.')), h('div.card', h('h3', 'Notes'), notes));
  }

  async function reload() { try { set(await api(cfg.sheetUrl)); } catch (e) { if (e.message !== 'auth') toast(e.message); } }
  function editing() { const ae = document.activeElement; return ae && root.contains(ae) && ae.matches('input, textarea, select'); }
  return {
    load, reload, render, go,
    setSheet: sh => set(sh),
    get: () => S.sheet,
    editing,
    updateLog(rolls) { if (S.logEl && S.logEl.isConnected) SR.renderLog(S.logEl, rolls); },
    mergeMe,
  };
}
return { mount, SECTIONS };
})();
