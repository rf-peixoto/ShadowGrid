/* Character sheet: used by the player app (/api/me/sheet) and the GM (/api/players/<id>/sheet). */
window.Sheet = (() => {
'use strict';
const AWAKENED = ['Magician', 'Aspected Magician', 'Adept', 'Mystic Adept'];
const CASTERS = ['Magician', 'Aspected Magician', 'Mystic Adept'];
const ADEPTS = ['Adept', 'Mystic Adept'];
const CORE = ['Body', 'Agility', 'Reaction', 'Strength', 'Willpower', 'Logic', 'Intuition', 'Charisma'];

function mount(root, cfg) {
  /* cfg: { gm: bool, sheetUrl, actionUrl, post(path, body) (player only), onSheet(sheet), openStore(), log: () => rolls, onRolled } */
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
      if (!quiet && sh.message && sh.message !== 'Saved.') toast(sh.message, 3500);
      return sh;
    } catch (e) { if (e.message !== 'auth') toast(e.message, 4500); render(); return null; }
  }
  const c = () => S.sheet.char, d = () => S.sheet.derived;
  const locked = () => S.sheet.locked;              // approved and not the GM
  const free = () => !S.sheet.locked;               // draft, or the GM
  const draft = () => !S.sheet.approved;
  const karmaCost = n => (S.sheet.approved && !cfg.gm ? n : 0);
  const costTag = n => karmaCost(n) ? ` · ${n} K` : '';
  async function confirmCost(text, n) { return !karmaCost(n) || UI.confirm(`${text} for ${n} Karma?`, { ok: 'Confirm' }); }

  function sections() {
    const ch = c(), list = [['overview', 'Overview'], ['attributes', 'Attributes'], ['skills', 'Skills'], ['qualities', 'Qualities']];
    if (AWAKENED.includes(ch.magic_type)) list.push(['magic', 'Magic']);
    if (ch.magic_type === 'Technomancer') list.push(['resonance', 'Resonance']);
    list.push(['matrix', 'Matrix'], ['gear', 'Gear'], ['combat', 'Combat'], ['contacts', 'Contacts'], ['background', 'Background & notes']);
    return list;
  }

  // ------------------------------------------------------------ render with focus restore
  function render() {
    if (!S.sheet) return;
    const ae = document.activeElement, fk = ae && main.contains(ae) ? ae.dataset.k : null;
    const page = root.closest('.page'), scroll = page ? page.scrollTop : 0;
    const secs = sections();
    if (!secs.some(([k]) => k === S.section)) S.section = 'overview';
    nav.innerHTML = '';
    for (const [k, label] of secs) {
      const badge = k === 'contacts' && S.sheet.player.pendingContacts ? h('span.badge', S.sheet.player.pendingContacts) : null;
      nav.append(h('button' + (S.section === k ? '.active' : ''), { type: 'button', onclick: () => go(k) }, label, badge));
    }
    main.innerHTML = '';
    main.append(header());
    const fn = { overview, attributes, skills, qualities, magic, resonance, matrix, gear, combat, contacts, background }[S.section] || overview;
    main.append(fn());
    if (fk) { const el = main.querySelector(`[data-k="${CSS.escape(fk)}"]`); if (el) el.focus(); }
    if (page) page.scrollTop = scroll;
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
        `${p.username} is still building this character.`,
        p.pendingContacts ? h('span.warn', ` ${p.pendingContacts} contact${p.pendingContacts > 1 ? 's' : ''} to confirm.`) : ''));
      if (st !== 'approved') b.append(h('button.primary', { type: 'button', onclick: () => review('approve') }, 'Approve sheet'));
      if (st === 'waiting') b.append(h('button', { type: 'button', onclick: () => review('return') }, 'Send back…'));
      if (st === 'approved') b.append(h('button', { type: 'button', onclick: () => review('reopen') }, 'Reopen for free editing'));
      b.append(h('button', { type: 'button', onclick: gmOverride }, 'Set Karma / Nuyen / Edge…'));
      wrap.append(b);
    } else if (st !== 'approved') {
      const b = h('div.banner' + (st === 'waiting' ? '.info' : '.warn'));
      if (st === 'waiting') b.append(h('p', SR.statusTag(st), ' Your GM is reviewing this sheet. You can keep editing until it is approved.'),
        h('button', { type: 'button', onclick: () => submit(false) }, 'Withdraw'));
      else b.append(h('p', h('b', 'Character creation. '), 'Edit freely within your metatype’s limits: purchases are refunded if you remove them and the store goes up to Availability 6. When you are done, send the sheet to your GM.',
        p.reviewNote ? h('span.warn', h('br'), 'GM note: ', p.reviewNote) : ''),
        h('button.primary', { type: 'button', onclick: () => submit(true) }, 'Submit for approval'));
      wrap.append(b);
    }
    const sub = [ch.metatype, ch.role, ch.magic_type !== 'Mundane' ? ch.magic_type : ''].filter(Boolean).join(' · ');
    const top = h('div.section-head',
      h('h2', ch.name || h('span.muted', 'Unnamed runner'), ' ', h('span.hint', sub)),
      h('div.row.tight', SR.healthTag(d().status), SR.statusChips(d().statuses),
        h('span.chip', h('span.k', 'Karma'), h('b', ch.karma)), h('span.chip', h('span.k', 'Nuyen'), h('b', { class: ch.nuyen < 0 ? 'bad' : '' }, money(ch.nuyen))),
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
    if (decision === 'approve' && !await UI.confirm('Approve this sheet? From now on the player spends Karma to improve, purchases are final and the store needs contacts. Edge is filled up and all contacts are confirmed.', { ok: 'Approve' })) return;
    try { set(await api(`/api/players/${S.sheet.player.id}/review`, 'POST', { decision, note })); toast(decision === 'approve' ? 'Sheet approved.' : 'Sheet sent back.'); } catch (e) { toast(e.message); }
  }
  async function gmOverride() {
    const ch = c();
    const k = h('input', { type: 'number', value: ch.karma }), n = h('input', { type: 'number', value: ch.nuyen }), e = h('input', { type: 'number', min: 0, max: 7, value: ch.current_edge });
    const ig = h('input', { type: 'number', min: 0, max: 20, value: ch.initiation_grade }), sg = h('input', { type: 'number', min: 0, max: 20, value: ch.submersion_grade });
    const ok = await UI.modal('GM override', h('div', h('p.hint', 'Sets exact values. Changes to Karma and Nuyen are recorded in the history. For awards to several players use the game page.'),
      h('div.form-grid', h('label', 'Karma', k), h('label', 'Nuyen', n), h('label', 'Current Edge (0-7)', e), h('label', 'Initiation grade', ig), h('label', 'Submersion grade', sg))), { ok: 'Apply', narrow: true });
    if (ok) act('admin_set', { karma: +k.value, nuyen: +n.value, current_edge: +e.value, initiation_grade: +ig.value, submersion_grade: +sg.value });
  }

  // ------------------------------------------------------------ helpers
  const field = (label, el, hint) => h('label', label, el, hint ? h('small.hint', hint) : null);
  function infoInput(key, { type = 'text', max, min } = {}) {
    return h('input', { type, value: c()[key] ?? '', 'data-k': 'info.' + key, max, min: type === 'number' ? (min ?? 0) : undefined,
      onchange: e => act('set_info', { [key]: type === 'number' ? +e.target.value : e.target.value }, { quiet: true }) });
  }
  function infoSelect(key, values, { lockedField = false, labels } = {}) {
    const dis = lockedField && locked();
    return h('select', { 'data-k': 'info.' + key, disabled: dis, onchange: e => act('set_info', { [key]: e.target.value }) },
      values.map(v => option(v, labels ? labels(v) : (v || 'None'), (c()[key] ?? '') === v)));
  }
  function stat(k, v, small, title) { return h('div.stat', { title: title || '' }, h('div.k', k), h('div.v', v, small ? h('small', small) : null)); }
  const pm = v => (v > 0 ? '+' : '') + v;
  function pickList(items, { search = true, render: rowFn, height = '52vh' }) {
    const q = h('input', { type: 'search', placeholder: 'Search…' });
    const list = h('div.pick-list', { style: { maxHeight: height, overflowY: 'auto' } });
    function draw() {
      list.innerHTML = '';
      const t = q.value.trim().toLowerCase();
      for (const it of items) if (!t || JSON.stringify(it).toLowerCase().includes(t)) list.append(rowFn(it));
      if (!list.children.length) list.append(h('p.hint', 'Nothing matches.'));
    }
    q.oninput = draw; draw();
    return h('div', search ? q : null, h('div.mt', list));
  }

  // ------------------------------------------------------------ overview
  function overview() {
    const ch = c(), dv = d();
    const out = h('div');
    const portrait = h('div.portrait', ch.portrait ? { style: { backgroundImage: `url("${ch.portrait}")` } } : {}, ch.portrait ? '' : 'No portrait');
    const file = h('input', { type: 'file', accept: 'image/*', hidden: true, onchange: e => loadPortrait(e.target.files[0]) });
    const pcol = h('div.col', portrait, h('div.row.tight', file, h('button.small', { type: 'button', onclick: () => file.click() }, ch.portrait ? 'Change' : 'Upload'),
      ch.portrait ? h('button.small.ghost', { type: 'button', onclick: () => act('set_portrait', { data: null }) }, 'Remove') : null));
    const meta = CAT.metatypes[ch.metatype];
    const form = h('div.form-grid',
      field('Name', infoInput('name')),
      field('Role', infoSelect('role', ['', ...CAT.roles]), 'A label only; no bonuses in SR6.'),
      field('Metatype', infoSelect('metatype', Object.keys(CAT.metatypes), { lockedField: true }), meta ? meta.desc : ''),
      field('Magic / Resonance', infoSelect('magic_type', CAT.magicTypes, { lockedField: true })),
      CASTERS.includes(ch.magic_type) ? field('Tradition', infoSelect('tradition', ['', ...Object.keys(CAT.traditions)], { lockedField: true, labels: v => v ? `${v} (drain: Willpower + ${CAT.traditions[v]})` : 'None' })) : null,
      ch.magic_type === 'Aspected Magician' ? field('Aspect', infoSelect('aspect', ['', ...CAT.aspects], { lockedField: true })) : null,
      AWAKENED.includes(ch.magic_type) ? field('Mentor spirit', infoSelect('mentor_spirit', ['', ...Object.keys(CAT.mentorSpirits)]), ch.mentor_spirit ? 'Take the Mentor Spirit quality for its benefits.' : '') : null,
      field('Lifestyle', infoSelect('lifestyle', Object.keys(CAT.lifestyles), { labels: v => `${v} (${money(CAT.lifestyles[v])}/month)` }),
        `${money(dv.lifestyle_cost)} per month${dv.lifestyle_mult !== 1 ? ` (×${dv.lifestyle_mult})` : ''}, charged by your GM.`),
      field('Age', infoInput('age', { type: 'number', max: 999 })),
      field('Reputation', infoInput('reputation', { type: 'number', max: 99, min: -99 })),
      field('Heat', infoInput('heat', { type: 'number', max: 99 })));
    out.append(h('div.card', h('div.overview-top', pcol, h('div', form,
      locked() ? h('p.hint', '🔒 Approved: metatype, magic type, tradition and aspect are set by the GM.') : null))));

    const racial = dv.qualities.filter(q => q.racial).map(q => q.name + (q.level > 1 ? ` ${q.level}` : ''));
    const extraVision = dv.vision.filter(v => !racial.some(r => r.toLowerCase().startsWith(v.toLowerCase())));
    out.append(h('div.card', h('h3', 'Quick stats', h('button.small', { type: 'button', onclick: () => go('combat') }, 'Combat ›')), h('div.stats',
      stat('Physical', `${Math.min(dv.physical_damage, dv.physical_boxes)}/${dv.physical_boxes}`),
      stat('Stun', `${dv.stun_damage}/${dv.stun_boxes}`),
      stat('Wound mod', dv.wound_modifier || '0'),
      stat('Initiative', `${dv.initiative_score} + ${dv.initiative_dice}D6`),
      stat('Major + Minor', `1 + ${dv.minor_actions}`, '', 'Actions each round: 1 Major plus Minor actions (1 + 1 per Initiative Die, max 5)'),
      stat('Defense Rating', dv.defense_rating),
      stat('Essence', dv.essence),
      AWAKENED.includes(ch.magic_type) ? stat('Magic', dv.attributes.Magic) : null,
      ch.magic_type === 'Technomancer' ? stat('Resonance', dv.attributes.Resonance) : null),
      racial.length || extraVision.length ? h('p.hint.mt', `${ch.metatype} abilities: ${racial.join(', ') || 'none'}.` + (extraVision.length ? ` Implants add ${extraVision.join(' and ')} vision.` : '')) : null));

    const nuyPerK = CAT.karma.nuyen_per_karma;
    const econ = h('div.card', h('h3', 'Karma & Nuyen'),
      h('div.stats', stat('Karma', ch.karma), stat('Nuyen', money(ch.nuyen)), stat('Gear value', money(dv.gear_value)), stat('Lifestyle', money(dv.lifestyle_cost), '/month')),
      ch.nuyen < 0 ? h('p.bad', 'You are in debt: your nuyen is negative.') : null,
      cfg.gm ? null : h('div.row.mt',
        h('button', { type: 'button', onclick: tradeKarma, disabled: !ch.karma }, `Trade Karma for Nuyen (1 = ${money(nuyPerK)})`),
        cfg.openStore ? h('button', { type: 'button', onclick: () => cfg.openStore() }, 'Open the store ›') : null),
      h('p.hint.mt', cfg.gm ? 'Changes you make here are free and are recorded in the history as GM changes.' :
        locked() ? 'Karma and Nuyen change through upgrades, purchases, sales, runs, lifestyle and GM awards. Every change is listed below.' :
          'While creating the character, removing purchases refunds them in full.'));
    out.append(econ);
    out.append(history());
    return out;
  }
  async function tradeKarma() {
    const v = await UI.prompt('Trade Karma for Nuyen', `How much Karma? (you have ${c().karma})`, { type: 'number', value: 1, min: 1, ok: 'Trade' });
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
    const ch = c(), dv = d();
    const names = [...CORE, 'Edge'];
    if (AWAKENED.includes(ch.magic_type)) names.push('Magic');
    if (ch.magic_type === 'Technomancer') names.push('Resonance');
    const t = h('table.list', h('thead', h('tr', h('th', 'Attribute'), h('th', 'Base'), h('th', 'Max'), h('th', 'Modifiers'), h('th', 'Rating'), h('th', ''))));
    const tb = h('tbody');
    for (const a of names) {
      const base = dv.base[a], mx = dv.max[a];
      const bonuses = (dv.bonuses[a] || []).map(([src, v]) => h('div.bonus' + (v < 0 ? '.neg' : ''), `${pm(v)} ${src}`));
      let baseCell = h('b', base), act2 = null;
      if (free()) baseCell = h('input', { type: 'number', min: 1, max: mx, value: base, 'data-k': 'attr.' + a,
        onchange: e => act('set_attribute', { attr: a, value: +e.target.value }, { quiet: true }) });
      else if (!cfg.gm && base < mx) {
        const cost = (base + 1) * CAT.karma.attribute;
        act2 = h('button.small', { type: 'button', disabled: ch.karma < cost, title: ch.karma < cost ? `Needs ${cost} Karma` : '',
          onclick: async () => { if (await UI.confirm(`Raise ${a} to ${base + 1} for ${cost} Karma?`, { ok: 'Raise' })) act('raise_attribute', { attr: a }); } }, `Raise · ${cost} K`);
      }
      tb.append(h('tr', h('td', a), h('td', baseCell), h('td.hint', mx), h('td', bonuses), h('td.attr-total', dv.attributes[a]), h('td.right', act2)));
    }
    tb.append(h('tr', h('td', 'Essence'), h('td', '6'), h('td.hint', '6'), h('td', dv.essence < 6 ? h('div.bonus.neg', `−${Math.round((6 - dv.essence) * 100) / 100} implants`) : null), h('td.attr-total', dv.essence), h('td')));
    t.append(tb);
    const head = h('div.row.between', h('p.hint.mb0', free() ? `Set base ratings within your metatype’s limits (${ch.metatype}). Augmentations add up to +4.`
      : `Raising an attribute costs the new rating × ${CAT.karma.attribute} Karma.`),
      free() && !cfg.gm ? h('button', { type: 'button', onclick: async () => { if (await UI.confirm('Roll every physical and mental attribute and Edge randomly within your metatype’s limits? This replaces the current base values.', { ok: 'Roll' })) act('autoroll'); } }, 'Random attributes') : null);
    const der = h('div.card', h('h3', 'Derived attributes'), h('div.stats',
      stat('Composure', dv.composure, '', 'Willpower + Charisma'), stat('Judge Intentions', dv.judge_intentions, '', 'Willpower + Intuition'),
      stat('Memory', dv.memory, '', 'Logic + Intuition'), stat('Lift / Carry', dv.lift_carry, '', 'Body + Willpower'),
      stat('Lift', `${dv.lift_kg} kg`, ` (${dv.overhead_kg} overhead)`), stat('Movement', `${dv.movement.walk} m`, ` / sprint ${dv.movement.sprint}+`),
      stat('Initiative', `${dv.initiative_score} + ${dv.initiative_dice}D6`),
      dv.astral_initiative ? stat('Astral init.', `${dv.astral_initiative.score} + ${dv.astral_initiative.dice}D6`) : null,
      dv.matrix.device ? stat('Matrix init.', `${dv.matrix.init_score} + ${dv.matrix.init_dice}D6`) : null));
    return h('div', h('div.card', head, h('div.table-wrap.mt', t)), der);
  }

  // ------------------------------------------------------------ skills
  function skills() {
    const ch = c(), pools = Object.fromEntries(S.sheet.pools.map(p => [p.key, p]));
    const max = free() ? (cfg.gm ? 12 : CAT.skillMaxCreation) : CAT.skillMax;
    const t = h('table.list', h('thead', h('tr', h('th', 'Skill'), h('th', 'Linked'), h('th', 'Rank'), h('th', 'Specialization (+2)'), h('th', 'Expertise (+3)'), h('th.right', 'Pool'))));
    const tb = h('tbody');
    for (const [s, info] of Object.entries(CAT.skills)) {
      const rank = ch.skills[s] || 0, spec = ch.specs[s] || '', exp = ch.expertise[s] || '';
      let rankCell;
      if (free()) rankCell = h('input', { type: 'number', min: 0, max, value: rank, 'data-k': 'skill.' + s,
        onchange: e => act('set_skill', { skill: s, rank: +e.target.value }, { quiet: true }) });
      else {
        const cost = (rank + 1) * CAT.karma.skill;
        rankCell = h('span.row.tight', h('b', rank), rank < max ? h('button.small', { type: 'button', disabled: ch.karma < cost,
          onclick: async () => { if (await UI.confirm(`${rank ? 'Raise' : 'Learn'} ${s} to ${rank + 1} for ${cost} Karma?`, { ok: 'Confirm' })) act('set_skill', { skill: s, rank: rank + 1 }); } }, `${rank ? 'Raise' : 'Learn'} · ${cost} K`) : null);
      }
      const opts = info.specs.filter(x => x !== exp);
      const specSel = h('select', { 'data-k': 'spec.' + s, disabled: !rank || (locked() && !!spec),
        title: locked() && !spec ? `Costs ${CAT.karma.specialization} Karma` : '',
        onchange: async e => {
          const v = e.target.value;
          if (locked() && v && !await UI.confirm(`Specialize in ${v} for ${CAT.karma.specialization} Karma?`, { ok: 'Confirm' })) { render(); return; }
          act('set_spec', { skill: s, spec: v }, { quiet: !locked() });
        } }, option('', rank ? 'None' : '—'), opts.map(x => option(x, x, x === spec)));
      let expCell;
      if (exp) expCell = h('span.row.tight', h('b', exp), free() ? h('button.small.ghost', { type: 'button', title: 'Remove expertise', onclick: () => act('set_expertise', { skill: s, clear: true }) }, '✕') : null);
      else if (info.exotic || !rank) expCell = h('span.hint', '—');
      else {
        const can = spec && rank >= 5;
        expCell = h('button.small', { type: 'button', disabled: !can, title: can ? `Turn ${spec} into expertise` : 'Needs a specialization and rank 5+',
          onclick: async () => { if (await confirmCost(`Turn ${spec} into expertise (+3)`, CAT.karma.expertise)) act('set_expertise', { skill: s }); } }, `Make expertise${costTag(CAT.karma.expertise)}`);
      }
      const best = [pools[`exp:${s}:${exp}`], pools[`spec:${s}:${spec}`], pools['skill:' + s]].filter(Boolean)[0];
      const untrained = !info.untrained && !rank;
      tb.append(h('tr' + (rank ? '' : '.dim'), h('td', s, untrained ? h('span.hint', ' (no untrained use)') : ''), h('td.hint', info.attr), h('td', rankCell), h('td', specSel), h('td', expCell),
        h('td.right', best ? h('b', { title: SR.breakdown(best.parts) }, best.value) : h('span.hint', '—'))));
    }
    t.append(tb);
    const skillCard = h('div.card', h('p.hint', free() ? `Skills go up to ${max} during creation. Pools add the linked attribute; untrained skills roll the attribute −1. Expertise needs a specialization and rank 5, then frees the specialization slot.` :
      `Raising a skill costs the new rank × ${CAT.karma.skill} Karma; a specialization or expertise costs ${CAT.karma.specialization} Karma.`), h('div.table-wrap', t));
    return h('div', skillCard, knowledgeCard());
  }
  function knowledgeCard() {
    const ch = c(), dv = d();
    const card = h('div.card', h('h3', 'Knowledge & languages', h('span.hint', draft() ? `Free at creation: ${dv.knowledge_used}/${dv.knowledge_free} (Logic)` : `New knowledge ${CAT.karma.knowledge} K · language level ${CAT.karma.language_level} K`)));
    const kl = h('div.chips-list');
    ch.knowledge.forEach((k, i) => kl.append(h('span.chip', k, free() ? h('button.x', { type: 'button', title: 'Remove', onclick: () => act('remove_knowledge', { index: i }) }, '×') : null)));
    const dl = h('datalist#knowledge-examples', CAT.knowledgeExamples.map(x => option(x)));
    const kin = h('input', { list: 'knowledge-examples', placeholder: 'e.g. Seattle Gangs', maxlength: 60 });
    const addK = async () => { const v = kin.value.trim(); if (!v) return; if (await confirmCost(`Learn ${v}`, CAT.karma.knowledge)) act('add_knowledge', { name: v }); };
    card.append(h('h4', 'Knowledge skills'), ch.knowledge.length ? kl : h('p.hint', 'None yet. Knowledge skills have no ranks: they let you use Perception or Memory on the subject.'),
      h('div.row.tight.mt', dl, kin, h('button.small', { type: 'button', onclick: addK }, `Add${costTag(CAT.karma.knowledge)}`)));
    const lt = h('div.col');
    const lv = CAT.languageLevels;
    ch.languages.forEach((l, i) => {
      const next = lv[lv.indexOf(l.level) + 1];
      const canRaise = l.level !== 'Native' && next && next !== 'Native';
      lt.append(h('div.row.tight', h('b', l.name), h('span.tag', l.level + (l.level === 'Specialist' ? ' +2' : l.level === 'Expert' ? ' +3' : '')),
        free() ? h('select', { onchange: e => act('set_language', { name: l.name, level: e.target.value }, { quiet: true }) }, lv.map(x => option(x, x, x === l.level))) :
          canRaise ? h('button.small', { type: 'button', onclick: async () => { if (await confirmCost(`Raise ${l.name} to ${next}`, CAT.karma.language_level)) act('set_language', { name: l.name, level: next }); } }, `→ ${next}${costTag(CAT.karma.language_level)}`) : null,
        free() ? h('button.small.danger', { type: 'button', onclick: () => act('remove_language', { index: i }) }, '✕') : null));
    });
    const ldl = h('datalist#language-examples', CAT.languageExamples.map(x => option(x)));
    const lin = h('input', { list: 'language-examples', placeholder: 'e.g. Sperethiel', maxlength: 40 });
    const lsel = h('select', lv.filter(x => draft() || cfg.gm || x === 'Basic').map(x => option(x)));
    const addL = async () => { const v = lin.value.trim(); if (!v) return; if (await confirmCost(`Learn ${v}`, CAT.karma.knowledge)) act('set_language', { name: v, level: lsel.value }); };
    card.append(h('h4.mt', 'Languages'), ch.languages.length ? lt : h('p.hint', 'Pick your native language (one is free at creation).'),
      h('div.row.tight.mt', ldl, lin, lsel, h('button.small', { type: 'button', onclick: addL }, `Add${costTag(CAT.karma.knowledge)}`)));
    return card;
  }

  // ------------------------------------------------------------ qualities
  function qualities() {
    const ch = c(), dv = d(), out = h('div');
    const cur = h('div.card', h('h3', 'Your qualities'));
    const list = h('div.pick-list');
    for (const q of dv.qualities.filter(x => x.racial)) {
      const meta = CAT.qualities[q.name];
      list.append(h('div.pick.have', h('div', h('div', '◆ ' + q.name + (q.level > 1 ? ` ${q.level}` : '')), h('div.meta', `${ch.metatype} ability · ${meta.desc}`))));
    }
    ch.qualities.forEach((q, i) => {
      const meta = CAT.qualities[q.name] || { karma: 0, desc: '' };
      const pos = meta.karma > 0, k = Math.abs(meta.karma) * (meta.levels ? q.level : 1);
      const lvl = meta.levels ? h('span.row.tight', h('button.small', { type: 'button', disabled: q.level <= 1, onclick: () => act('set_quality_level', { index: i, level: q.level - 1 }) }, '−'),
        h('b', `Level ${q.level}`), h('button.small', { type: 'button', disabled: q.level >= meta.levels, onclick: () => act('set_quality_level', { index: i, level: q.level + 1 }) }, '+')) : null;
      const canRemove = free() || !pos;
      const removeCost = locked() && !pos ? ` · ${k * CAT.karma.quality_mult} K` : '';
      list.append(h('div.pick.have', h('div', h('div', (pos ? '＋ ' : '－ ') + q.name + (q.choice ? ` (${q.choice})` : '')), h('div.meta', `${meta.desc} · ${k} Karma`)),
        h('span.row.tight', lvl, canRemove ? h('button.small.danger', { type: 'button', onclick: async () => {
          if (locked() && !await UI.confirm(`Buy off ${q.name} for ${k * CAT.karma.quality_mult} Karma?`, { ok: 'Buy off' })) return;
          act('remove_quality', { index: i });
        } }, locked() ? `Buy off${removeCost}` : 'Remove') : null)));
    });
    if (!list.children.length) list.append(h('p.hint', 'None yet.'));
    cur.append(list);
    if (locked()) cur.append(h('p.hint.mt', `After approval a positive quality costs ${CAT.karma.quality_mult}× its Karma and a negative one can be bought off for ${CAT.karma.quality_mult}× its bonus. New negative qualities come from the GM.`));
    out.append(cur);
    for (const side of ['Positive', 'Negative']) {
      if (locked() && side === 'Negative') continue;
      const items = Object.entries(CAT.qualities).filter(([, q]) => side === 'Positive' ? q.karma > 0 : q.karma <= 0).map(([name, q]) => ({ name, ...q }));
      const card = h('div.card', h('h3', `${side} qualities`, h('span.hint', side === 'Positive' ? (locked() ? `cost ${CAT.karma.quality_mult}× Karma` : 'cost Karma') : 'give Karma')));
      card.append(pickList(items, { height: '40vh', render: q => {
        const k = Math.abs(q.karma) * (locked() ? CAT.karma.quality_mult : 1);
        return h('div.pick', h('div', h('div', q.name + (q.levels ? ` (1-${q.levels})` : '')), h('div.meta', `${q.desc} · ${k} Karma${q.levels ? ' per level' : ''}${q.choice ? ` · choose ${q.choice}` : ''}`)),
          h('button.small', { type: 'button', disabled: side === 'Positive' && !cfg.gm && ch.karma < k, onclick: () => addQuality(q) }, 'Add'));
      } }));
      out.append(card);
    }
    return out;
  }
  async function addQuality(q) {
    let level = 1, choice = '';
    if (q.levels || q.choice) {
      const lv = h('input', { type: 'number', min: 1, max: q.levels || 1, value: 1 });
      let ch;
      if (q.choice === 'attribute') ch = h('select', CORE.map(a => option(a)));
      else if (q.choice === 'skill') ch = h('select', Object.keys(CAT.skills).map(a => option(a)));
      else if (q.choice === 'mentor') ch = h('select', Object.keys(CAT.mentorSpirits).map(a => option(a)));
      else if (q.choice) ch = h('input', { required: true, placeholder: q.choice });
      const ok = await UI.modal(q.name, h('div', h('p.hint', q.desc), q.levels ? h('label.stack', `Level (1-${q.levels})`, lv) : null, ch ? h('label.stack', `Choice: ${q.choice}`, ch) : null), { ok: 'Add', narrow: true });
      if (!ok) return;
      level = +lv.value || 1; choice = ch ? ch.value : '';
    }
    const k = Math.abs(q.karma) * level * (locked() ? CAT.karma.quality_mult : 1);
    if (locked() && !await UI.confirm(`Take ${q.name} for ${k} Karma?`, { ok: 'Confirm' })) return;
    act('add_quality', { quality: q.name, level, choice });
  }

  // ------------------------------------------------------------ magic
  function magic() {
    const ch = c(), dv = d(), out = h('div');
    const A = dv.attributes;
    out.append(h('div.card', h('h3', ch.magic_type, ch.tradition ? h('span.hint', `${ch.tradition} tradition`) : null), h('div.stats',
      stat('Magic', A.Magic, ` / max ${dv.max.Magic}`), stat('Initiate grade', ch.initiation_grade),
      CASTERS.includes(ch.magic_type) ? stat('Spell AR', dv.spell_ar, '', `Magic + ${dv.tradition_attr}`) : null,
      stat('Drain pool', dv.drain_pool, '', CASTERS.includes(ch.magic_type) ? `Willpower + ${dv.tradition_attr}` : 'Body + Willpower'),
      stat('Astral init.', `${dv.astral_initiative.score} + 2D6`),
      dv.power_focus ? stat('Power focus', `+${dv.power_focus}`) : null),
      CASTERS.includes(ch.magic_type) && !ch.tradition ? h('p.warn', 'Pick a tradition on the Overview: it sets your drain attribute.') : null,
      ch.mentor_spirit ? h('p.hint', `${ch.mentor_spirit}: ${CAT.mentorSpirits[ch.mentor_spirit]}`) : null));
    if (CASTERS.includes(ch.magic_type)) out.append(spellsCard());
    if (ADEPTS.includes(ch.magic_type)) out.append(powersCard());
    out.append(fociCard());
    if (['Magician', 'Mystic Adept'].includes(ch.magic_type) || (ch.magic_type === 'Aspected Magician' && ch.aspect === 'Conjuring')) out.append(spiritsCard());
    out.append(initiationCard(false));
    return out;
  }
  function spellsCard() {
    const ch = c();
    const card = h('div.card', h('h3', 'Spells & rituals', h('span.row.tight',
      h('button.small', { type: 'button', onclick: learnSpell }, `Learn${costTag(CAT.karma.spell)}`),
      free() ? h('button.small.ghost', { type: 'button', onclick: customSpell }, 'Custom…') : null)));
    if (!ch.spells.length) { card.append(h('p.hint', 'No spells yet.')); return card; }
    const t = h('table.list', h('thead', h('tr', h('th', 'Spell'), h('th', 'Category'), h('th', 'Type'), h('th', 'Range'), h('th', 'Dur.'), h('th', 'Drain'), h('th', ''))));
    const tb = h('tbody');
    ch.spells.forEach((sp, i) => tb.append(h('tr', h('td', h('b', sp.name), sp._custom ? h('span.tag.custom', ' custom') : '', h('div.hint', sp.desc || '')),
      h('td', sp.category + (sp.kind ? ` · ${sp.kind}` : '') + (sp.damage ? ` · ${sp.damage === 'S' ? 'Stun' : 'Physical'} damage` : '')), h('td', sp.type === 'M' ? 'Mana' : sp.type === 'P' ? 'Physical' : ''), h('td', sp.range || ''), h('td', sp.duration || ''),
      h('td', sp.category === 'Ritual' ? `threshold ${sp.threshold}` : sp.drain),
      h('td.right', free() ? h('button.small.danger', { type: 'button', onclick: () => act('forget_spell', { index: i }) }, '✕') : null))));
    t.append(tb);
    card.append(h('div.table-wrap', t), h('p.hint', 'Casting from the dice roller rolls the drain right after. Combat spells against enemies are resolved by the GM on the map.'));
    return card;
  }
  async function learnSpell() {
    const have = new Set(c().spells.map(s => s.name));
    let chosen = null;
    const items = [...CAT.spells.map(s => ({ ...s, kindOf: 'spell' })), ...CAT.rituals.map(r => ({ ...r, category: 'Ritual', kindOf: 'ritual' }))].filter(s => !have.has(s.name));
    const body = pickList(items, { render: s => h('label.pick', { title: s.desc }, h('div', h('div', s.name), h('div.meta',
      s.kindOf === 'ritual' ? `Ritual · ${s.keywords} · threshold ${s.threshold}` : `${s.category}${s.kind ? ' · ' + s.kind : ''} · ${s.range} · ${s.type === 'M' ? 'Mana' : 'Physical'} · drain ${s.drain}${s.damage ? ' · ' + s.damage : ''}`), h('div.meta', s.desc)),
      h('input', { type: 'radio', name: 'sp', onchange: () => { chosen = s.name; } })) });
    if (await UI.modal('Learn a spell or ritual', body, { ok: `Learn${costTag(CAT.karma.spell)}`, wide: true }) && chosen) act('learn_spell', { name: chosen });
  }
  async function customSpell() {
    const name = h('input', { required: true }), cat = h('select', ['Combat', 'Detection', 'Health', 'Illusion', 'Manipulation'].map(x => option(x)));
    const kind = h('select', option('', '—'), option('Direct'), option('Indirect')), type = h('select', option('P', 'Physical'), option('M', 'Mana'));
    const drain = h('input', { type: 'number', min: 0, max: 12, value: 3 }), dmg = h('select', option('', '—'), option('P'), option('S'));
    const desc = h('textarea', { rows: 2 });
    if (!await UI.modal('Custom spell', h('div', h('div.form-grid', h('label', 'Name', name), h('label', 'Category', cat), h('label', 'Combat kind', kind), h('label', 'Type', type),
      h('label', 'Drain', drain), h('label', 'Damage', dmg)), h('label.stack', 'Description', desc)), { ok: 'Add' })) return;
    act('learn_spell', { custom: { name: name.value, category: cat.value, kind: kind.value, type: type.value, drain: +drain.value, damage: dmg.value, desc: desc.value } });
  }
  function powersCard() {
    const ch = c(), dv = d();
    const over = dv.power_points_used > dv.power_points_available;
    const card = h('div.card', h('h3', h('span', 'Adept powers ', h('span.chip', { class: over ? 'bad' : '' }, `Power Points ${dv.power_points_used} / ${dv.power_points_available}`)),
      h('span.row.tight', h('button.small', { type: 'button', onclick: addPower }, 'Add a power'),
        ch.magic_type === 'Mystic Adept' ? h('button.small', { type: 'button', onclick: async () => { if (await confirmCost('Buy a power point', 5)) act('buy_power_point'); } }, `Buy power point${costTag(5)}`) : null)));
    if (over) card.append(h('p.bad', 'You are using more Power Points than you have.'));
    if (!ch.powers.length) { card.append(h('p.hint', 'No powers yet.')); return card; }
    const byName = Object.fromEntries(CAT.powers.map(p => [p.name, p]));
    const t = h('table.list', h('thead', h('tr', h('th', 'Power'), h('th', 'Level'), h('th', 'PP'), h('th', 'Activation'), h('th', ''))));
    const tb = h('tbody');
    ch.powers.forEach((p, i) => {
      const m = byName[p.name] || {};
      const cost = (p.name === 'Improved Ability' && ['Close Combat', 'Firearms', 'Exotic Weapons', 'Athletics'].includes(p.choice) ? m.combat_cost : m.cost) * (m.levels ? p.level : 1);
      tb.append(h('tr', h('td', h('b', p.name), p.choice ? ` (${p.choice})` : '', h('div.hint', m.desc || '')),
        h('td', m.levels ? h('span.row.tight', h('button.small', { type: 'button', disabled: p.level <= 1 || locked(), onclick: () => act('set_power', { index: i, level: p.level - 1 }) }, '−'), h('b', p.level),
          h('button.small', { type: 'button', disabled: m.max && p.level >= m.max, onclick: () => act('set_power', { index: i, level: p.level + 1 }) }, '+')) : '—'),
        h('td', Math.round(cost * 100) / 100), h('td', m.activation || ''),
        h('td.right', free() ? h('button.small.danger', { type: 'button', onclick: () => act('remove_power', { index: i }) }, '✕') : null)));
    });
    t.append(tb);
    card.append(h('div.table-wrap', t));
    return card;
  }
  async function addPower() {
    let chosen = null;
    const choice = h('select', { hidden: true });
    const body = h('div', pickList(CAT.powers, { render: p => h('label.pick', h('div', h('div', p.name), h('div.meta', `${p.cost} PP${p.levels ? ' per level' : ''} · ${p.activation} · ${p.desc}`)),
      h('input', { type: 'radio', name: 'pw', onchange: () => {
        chosen = p; choice.innerHTML = '';
        if (p.choice === 'Physical attribute') choice.append(...['Body', 'Agility', 'Reaction', 'Strength'].map(a => option(a)));
        else if (p.choice === 'Skill') choice.append(...Object.keys(CAT.skills).map(a => option(a)));
        else if (p.choice) choice.append(...['Sight', 'Hearing', 'Smell', 'Taste', 'Touch'].map(a => option(a)));
        choice.hidden = !p.choice;
      } })) }), h('label.stack.mt', 'Choice (if the power needs one)', choice));
    if (await UI.modal('Add an adept power', body, { ok: 'Add', wide: true }) && chosen) act('set_power', { name: chosen.name, choice: chosen.choice ? choice.value : '', level: 1 });
  }
  function fociCard() {
    const ch = c();
    const foci = ch.inventory.filter(it => it.focus);
    const card = h('div.card', h('h3', 'Foci', cfg.openStore ? h('button.small', { type: 'button', onclick: () => cfg.openStore('Magic') }, 'Buy foci ›') : null));
    card.append(h('p.hint', `Bonding costs Force × the focus type’s Karma (${Object.entries(CAT.focusBond).map(([k, v]) => `${k} ×${v}`).join(', ')}). You can bond up to Magic foci. A bonded power focus adds its Force to magic dice pools.`));
    if (!foci.length) { card.append(h('p.hint', 'No foci.')); return card; }
    const t = h('table.list', h('thead', h('tr', h('th', 'Focus'), h('th', 'Type'), h('th', 'Force'), h('th', ''))));
    const tb = h('tbody');
    for (const f of foci) {
      const cost = (f.force || 1) * (CAT.focusBond[f.focus] || 2);
      tb.append(h('tr', h('td', f.name), h('td', f.focus), h('td', f.force),
        h('td.right', h('button.small' + (f.bonded ? '.good' : ''), { type: 'button', disabled: f.bonded && locked(),
          onclick: async () => { if (!f.bonded && !cfg.gm && !await UI.confirm(`Bond ${f.name} for ${cost} Karma?`, { ok: 'Bond' })) return; act('bond_focus', { uid: f.uid }); } },
        f.bonded ? '✓ Bonded' : `Bond · ${cost} K`))));
    }
    t.append(tb);
    card.append(h('div.table-wrap', t));
    return card;
  }
  function spiritsCard() {
    const ch = c(), dv = d();
    const used = ch.spirits.reduce((a, s) => a + s.force, 0);
    const card = h('div.card', h('h3', 'Spirits', h('span.row.tight', h('span.hint', `Force in use ${used} / ${dv.spirit_force_limit}`),
      h('button.small', { type: 'button', onclick: summon, disabled: !cfg.gm && !S.sheet.pools.some(p => p.key === 'summon') }, 'Summon…'))));
    if (!ch.spirits.length) { card.append(h('p.hint', 'Summoning rolls Conjuring + Magic against the spirit (Force × 2 dice). Net hits are services; the spirit’s hits are your drain.')); return card; }
    ch.spirits.forEach((s, i) => {
      const st = (S.sheet.spirits || [])[i] || null;
      const block = st ? h('div.hint', Object.entries(st.attrs).map(([k, v]) => `${k.slice(0, 3).toUpperCase()} ${v}`).join(' · '),
        h('br'), `Init ${st.init} + ${st.init_dice}D6 · DR ${st.dr} · Monitor ${st.cm} · Move ${st.move}`, h('br'),
        `Attacks: ${st.attacks.map(a => `${a.name} ${a.dv} AR ${a.ar}`).join('; ') || '—'}`, h('br'), `Powers: ${st.powers.join(', ')}`) : null;
      card.append(h('div.spirit', h('div.row.between', h('b', `${s.type} spirit · Force ${s.force}`),
        h('span.row.tight', h('span', 'Services'), h('button.small', { type: 'button', onclick: () => act('set_spirit', { index: i, services: s.services - 1 }) }, '−'), h('b', s.services),
          h('button.small', { type: 'button', disabled: !cfg.gm, title: cfg.gm ? '' : 'Only the GM adds services', onclick: () => act('set_spirit', { index: i, services: s.services + 1 }) }, '+'),
          h('label.check', h('input', { type: 'checkbox', checked: s.bound, onchange: e => act('set_spirit', { index: i, bound: e.target.checked }, { quiet: true }) }), 'Bound'),
          h('button.small.danger', { type: 'button', onclick: () => act('release_spirit', { index: i }) }, 'Release'))), block));
    });
    return card;
  }
  async function summon() {
    const type = h('select', CAT.spirits.map(s => option(s))), force = h('input', { type: 'number', min: 1, max: d().attributes.Magic * 2 || 12, value: Math.min(3, d().attributes.Magic || 3) });
    const ok = await UI.modal('Summon a spirit', h('div', h('div.form-grid', h('label', 'Type', type), h('label', 'Force', force)),
      h('p.hint', 'Rolls your Conjuring + Magic against Force × 2 dice. Drain equals the spirit’s hits (Physical if that is more than your Magic).')), { ok: 'Summon', narrow: true });
    if (ok) act('summon', { type: type.value, force: +force.value });
  }
  function initiationCard(tm) {
    const ch = c();
    const grade = tm ? ch.submersion_grade : ch.initiation_grade;
    const list = tm ? ch.echoes : ch.metamagics;
    const cost = (tm ? CAT.karma.submersion_base : CAT.karma.initiation_base) + grade + 1;
    const card = h('div.card', h('h3', tm ? `Submersion · grade ${grade}` : `Initiation · grade ${grade}`,
      h('button.small', { type: 'button', onclick: () => initiate(tm) }, `${tm ? 'Submerge' : 'Initiate'} to ${grade + 1}${costTag(cost)}`)),
      list.length ? h('div.chips-list', list.map(x => h('span.chip', x))) : h('p.hint', tm ? 'Each grade raises your Resonance maximum by 1 and gives an echo.' : 'Each grade raises your Magic maximum by 1 and gives a metamagic.'));
    return card;
  }
  async function initiate(tm) {
    const ch = c();
    const grade = (tm ? ch.submersion_grade : ch.initiation_grade) + 1;
    const cost = (tm ? CAT.karma.submersion_base : CAT.karma.initiation_base) + grade;
    const src = tm ? CAT.echoes : CAT.metamagics.filter(m => !m.adept_only || ADEPTS.includes(ch.magic_type));
    const have = new Set(tm ? ch.echoes : ch.metamagics);
    let chosen = null;
    const body = pickList(src.filter(m => m.repeatable || !have.has(m.name)), { search: false, render: m => h('label.pick', h('div', h('div', m.name), h('div.meta', m.desc)),
      h('input', { type: 'radio', name: 'mm', onchange: () => { chosen = m.name; } })) });
    if (await UI.modal(`${tm ? 'Submersion' : 'Initiation'} grade ${grade}${karmaCost(cost) ? ` (${cost} Karma)` : ''}`, body, { ok: tm ? 'Submerge' : 'Initiate' }) && chosen) act('initiate', { pick: chosen });
  }

  // ------------------------------------------------------------ resonance
  function resonance() {
    const ch = c(), dv = d(), A = dv.attributes, out = h('div');
    out.append(h('div.card', h('h3', 'Technomancer'), h('div.stats', stat('Resonance', A.Resonance, ` / max ${dv.max.Resonance}`), stat('Submersion', ch.submersion_grade),
      stat('Fading pool', dv.fading_pool, '', 'Willpower + Logic'), stat('Form AR', dv.form_ar, '', 'Electronics + Resonance'),
      stat('Persona', `A${A.Charisma} S${A.Intuition} D${A.Logic} F${A.Willpower}`, '', 'Attack = CHA, Sleaze = INT, Data Processing = LOG, Firewall = WIL'))));
    const fc = h('div.card', h('h3', 'Complex forms', h('button.small', { type: 'button', onclick: learnForm }, `Learn${costTag(CAT.karma.complex_form)}`)));
    if (!ch.complex_forms.length) fc.append(h('p.hint', 'No complex forms yet.'));
    else {
      const byName = Object.fromEntries(CAT.complexForms.map(f => [f.name, f]));
      const t = h('table.list', h('thead', h('tr', h('th', 'Form'), h('th', 'Fade'), h('th', 'Duration'), h('th', ''))));
      const tb = h('tbody');
      ch.complex_forms.forEach((f, i) => { const m = byName[f.name] || {}; tb.append(h('tr', h('td', h('b', f.name), f.choice ? ` (${f.choice})` : '', h('div.hint', m.desc || '')), h('td', m.fade), h('td', m.duration),
        h('td.right', free() ? h('button.small.danger', { type: 'button', onclick: () => act('forget_form', { index: i }) }, '✕') : null))); });
      t.append(tb); fc.append(h('div.table-wrap', t), h('p.hint', 'Threading from the dice roller rolls fading right after.'));
    }
    out.append(fc);
    const sc = h('div.card', h('h3', 'Sprites', h('span.row.tight', h('span.hint', `Registered ${ch.sprites.filter(s => s.registered).length} / ${dv.sprite_limit}`),
      h('button.small', { type: 'button', onclick: compile }, 'Compile…'))));
    if (!ch.sprites.length) sc.append(h('p.hint', 'Compiling rolls Tasking + Resonance against Level × 2 dice; net hits are tasks and the sprite’s hits are your fading.'));
    ch.sprites.forEach((s, i) => {
      const m = CAT.sprites[s.type] || {};
      sc.append(h('div.spirit', h('div.row.between', h('b', `${s.type} sprite · Level ${s.level}`),
        h('span.row.tight', h('span', 'Tasks'), h('button.small', { type: 'button', onclick: () => act('set_sprite', { index: i, tasks: s.tasks - 1 }) }, '−'), h('b', s.tasks),
          h('button.small', { type: 'button', disabled: !cfg.gm, onclick: () => act('set_sprite', { index: i, tasks: s.tasks + 1 }) }, '+'),
          h('label.check', h('input', { type: 'checkbox', checked: s.registered, onchange: e => act('set_sprite', { index: i, registered: e.target.checked }) }), 'Registered'),
          h('button.small.danger', { type: 'button', onclick: () => act('release_sprite', { index: i }) }, 'Release'))),
        h('div.hint', `A ${s.level + m.attack} · S ${s.level + m.sleaze} · D ${s.level + m.data_processing} · F ${s.level + m.firewall} · Init ${s.level * 2 + m.init} + 4D6 · Skills ${(m.skills || []).join(', ')} · Powers ${(m.powers || []).join(', ')}`)));
    });
    out.append(sc, initiationCard(true));
    return out;
  }
  async function learnForm() {
    const have = new Set(c().complex_forms.map(f => f.name));
    let chosen = null;
    const body = pickList(CAT.complexForms.filter(f => !have.has(f.name)), { render: f => h('label.pick', h('div', h('div', f.name), h('div.meta', `Fade ${f.fade} · ${f.duration} · ${f.desc}`)),
      h('input', { type: 'radio', name: 'cf', onchange: () => { chosen = f.name; } })) });
    if (await UI.modal('Learn a complex form', body, { ok: `Learn${costTag(CAT.karma.complex_form)}`, wide: true }) && chosen) act('learn_form', { name: chosen });
  }
  async function compile() {
    const type = h('select', Object.keys(CAT.sprites).map(s => option(s))), lvl = h('input', { type: 'number', min: 1, max: d().attributes.Resonance * 2 || 12, value: Math.min(3, d().attributes.Resonance || 3) });
    if (await UI.modal('Compile a sprite', h('div', h('div.form-grid', h('label', 'Type', type), h('label', 'Level', lvl))), { ok: 'Compile', narrow: true })) act('compile', { type: type.value, level: +lvl.value });
  }

  // ------------------------------------------------------------ matrix
  function matrix() {
    const ch = c(), dv = d(), mx = dv.matrix;
    const decks = ch.inventory.filter(it => it.sub === 'Cyberdecks'), links = ch.inventory.filter(it => it.sub === 'Commlinks' || it.ref === 'cyberware-commlink-headware');
    const devOpts = [...decks, ...links].map(it => option(it.uid, `${it.name}${it.sub === 'Cyberdecks' ? ' (deck)' : ''}`, mx.device === it.uid));
    if (ch.magic_type === 'Technomancer') devOpts.unshift(option('persona', 'Living persona', mx.device === 'persona'));
    const card = h('div.card', h('h3', 'Matrix'));
    if (!devOpts.length) { card.append(h('p.hint', 'You have no cyberdeck or commlink. Buy one in the store (Electronics or Cyberdecks & Software).')); return card; }
    card.append(h('div.form-grid', h('label', 'Active device', h('select', { onchange: e => act('set_matrix', { device: e.target.value }, { quiet: true }) }, devOpts)),
      h('label', 'Mode', h('select', { onchange: e => act('set_matrix', { mode: e.target.value }, { quiet: true }) }, CAT.matrixModes.map(m => option(m, m, m === mx.mode))))));
    card.append(h('div.stats.mt', stat('Attack', mx.attack), stat('Sleaze', mx.sleaze), stat('Data Proc.', mx.data_processing), stat('Firewall', mx.firewall),
      stat('Matrix AR', mx.ar, '', 'Attack + Sleaze'), stat('Matrix DR', mx.dr, '', 'Data Processing + Firewall'), stat('Initiative', `${mx.init_score} + ${mx.init_dice}D6`),
      stat('Device Rating', mx.device_rating)));
    const cm = { p: mx.damage, pm: mx.boxes, s: 0, sm: 0, ov: 0 };
    card.append(h('div.mt', SR.monitor('physical', cm, { label: 'Matrix damage', onSet: (_t, v) => act('set_matrix', { damage: v }, { quiet: true }), showTools: false })));
    if (mx.device !== 'persona') {
      const jack = ch.inventory.find(it => it.implant && it.data_processing);
      card.append(h('p.hint', jack ? `Data Processing and Firewall come from your ${jack.name}.` : 'A cyberdeck takes Data Processing and Firewall from a cyberjack (or your best commlink).'));
    }
    const progs = ch.inventory.filter(it => it.sub === 'Software' && (it.ref || '').startsWith('cyberdecks-software-cyberprogram'));
    const pc = h('div.card', h('h3', 'Programs', h('span.hint', `${mx.programs.filter(p => p.running).length} / ${mx.slots} running`)));
    if (!progs.length) pc.append(h('p.hint', 'Buy “Cyberprogram, Basic” or “Cyberprogram, Hacking” in the store, then choose which program each one is.'));
    for (const it of progs) {
      const hacking = (it.ref || '').includes('hacking');
      const choices = [...Object.keys(CAT.programs.Basic), ...(hacking ? Object.keys(CAT.programs.Hacking) : [])];
      const desc = it.choice ? (CAT.programs.Basic[it.choice] || CAT.programs.Hacking[it.choice]) : '';
      pc.append(h('div.row.tight', h('select', { onchange: e => act('set_program', { uid: it.uid, choice: e.target.value }, { quiet: true }) }, option('', `${it.name}: choose…`), choices.map(x => option(x, x, x === it.choice))),
        h('label.check', h('input', { type: 'checkbox', checked: !!it.running, onchange: e => act('set_program', { uid: it.uid, running: e.target.checked }, { quiet: true }) }), 'Running'),
        h('span.hint', desc)));
    }
    return h('div', card, pc);
  }

  // ------------------------------------------------------------ gear (inventory)
  function gear() {
    const ch = c(), dv = d(), out = h('div');
    out.append(h('div.card', h('div.stats', stat('Defense Rating', dv.defense_rating, '', dv.armor_parts.map(([k, v]) => `${k} +${v}`).join(', ')), stat('Essence', dv.essence),
      stat('Gear value', money(dv.gear_value)), stat('Nuyen', money(ch.nuyen)), S.sheet.approved ? stat('Store pays', `${S.sheet.sellPct}%`) : null),
      h('div.row.mt', cfg.openStore ? h('button.primary', { type: 'button', onclick: () => cfg.openStore() }, 'Buy gear in the store ›') : null,
        cfg.gm ? h('button', { type: 'button', onclick: gmGive }, 'Give an item…') : null,
        h('span.hint', cfg.gm ? 'GM changes are free.' : draft() ? 'Returning an item refunds its full price while you create the character.' :
          `Selling pays ${S.sheet.sellPct}% of the price, through a contact who could get that item.`))));
    const byCat = {};
    for (const it of ch.inventory) (byCat[it.cat] = byCat[it.cat] || []).push(it);
    let any = false;
    for (const cat of [...CAT.store.categories, ...Object.keys(byCat).filter(k => !CAT.store.categories.includes(k))]) {
      const items = byCat[cat]; if (!items) continue;
      any = true;
      const t = h('table.list', h('thead', h('tr', h('th', 'Item'), h('th', 'Stats'), h('th', 'Qty / ammo'), h('th', ''))));
      const tb = h('tbody');
      for (const it of items) tb.append(gearRow(it));
      t.append(tb);
      out.append(h('div.card', h('h3', cat, h('span.hint', `${items.length} item${items.length > 1 ? 's' : ''}`)), h('div.table-wrap', t)));
    }
    if (!any) out.append(h('div.card.empty', h('h3', 'No gear yet'), h('p', 'Weapons, armor, ammo, cyberware, vehicles and everything else is bought in the store.')));
    return out;
  }
  function gearRow(it) {
    const dv = d();
    const equippable = ['Melee', 'Ranged', 'Armor'].includes(it.cat) && !it.mod;
    const on = it.equipped !== false;
    const btns = [];
    if (equippable) btns.push(h('button.small' + (on ? '.good' : ''), { type: 'button', onclick: () => act('toggle_equipped', { uid: it.uid }, { quiet: true }), title: on ? 'Equipped: click to store' : 'Stored: click to equip' }, on ? '✓ Equipped' : 'Equip'));
    if (it.clip) {
      btns.push(h('button.small', { type: 'button', onclick: () => reloadWeapon(it) }, 'Reload'));
      if (it.loaded && it.loaded.rounds) btns.push(h('button.small.ghost', { type: 'button', onclick: () => act('unload', { uid: it.uid }) }, 'Unload'));
      if (cfg.gm) btns.push(h('button.small.ghost', { type: 'button', onclick: async () => { const v = await UI.prompt('Set loaded rounds', `0-${it.clip}`, { type: 'number', value: it.loaded.rounds, min: 0 }); if (v !== null) act('set_ammo', { uid: it.uid, rounds: +v }); } }, 'Set ammo'));
    }
    if (it.focus) btns.push(h('button.small' + (it.bonded ? '.good' : ''), { type: 'button', disabled: it.bonded && locked(), onclick: () => act('bond_focus', { uid: it.uid }) }, it.bonded ? '✓ Bonded' : 'Bond'));
    if (it.sub === 'Software' && (it.ref || '').startsWith('cyberdecks-software-cyberprogram')) btns.push(h('button.small.ghost', { type: 'button', onclick: () => go('matrix') }, 'Programs ›'));
    btns.push(h('button.small.ghost', { type: 'button', onclick: () => editGear(it) }, 'Edit'));
    if (draft() && !cfg.gm) btns.push(h('button.small.danger', { type: 'button', title: 'Full refund during creation', onclick: () => act('remove_item', { uid: it.uid }) }, 'Return'));
    else if (!cfg.gm) {
      const acc = S.sheet.store[it.ref];
      const canSell = !it.ref || !acc || acc[0];
      const unit = it.unit === 'rounds' ? (it.cost || 0) / 10 : (it.cost || 0);
      const price = Math.floor(unit * (it.qty || 1) * S.sheet.sellPct / 100);
      btns.push(h('button.small', { type: 'button', disabled: !canSell, title: canSell ? '' : (acc ? acc[1] : ''), onclick: () => sell(it, unit) }, `Sell${it.qty > 1 && !it.unit ? '' : ` · ${money(price)}`}`));
      btns.push(h('button.small.danger', { type: 'button', onclick: async () => { if (await UI.confirm(`Throw away ${it.name}? You get nothing for it.`, { ok: 'Discard', danger: true })) act('remove_item', { uid: it.uid }); } }, '✕'));
    } else btns.push(h('button.small.danger', { type: 'button', onclick: async () => { if (await UI.confirm(`Remove ${it.name}?`, { ok: 'Remove', danger: true })) act('remove_item', { uid: it.uid }); } }, '✕'));
    let qtyCell = it.qty > 1 || it.unit ? `${it.qty} ${it.unit || ''}`.trim() : '';
    if (it.clip) {
      const l = it.loaded || { rounds: 0, type: 'Regular' };
      qtyCell = h('span', { class: l.rounds ? '' : 'bad' }, `${l.rounds}/${it.clip}${l.rounds && l.type !== 'Regular' ? ' ' + l.type : ''}`);
    }
    if (it.cat === 'Vehicles' || it.cat === 'Drones') {
      const v = (dv.vehicles || []).find(x => x.uid === it.uid);
      if (v) qtyCell = h('div', SR.monitor('physical', { p: v.damage, pm: v.boxes, s: 0, sm: 0, ov: 0 }, { compact: true, showTools: false, label: 'Damage',
        onSet: (_t, val) => act('set_vehicle_damage', { uid: it.uid, value: val }, { quiet: true }) }));
    }
    const sub = [it.sub, it.grade && it.grade !== 'Standard' ? it.grade : '', it.implant ? `Essence ${it.essence}` : '', it.avail != null && it.ref ? `Avail ${SR.availText(it.avail, it.legal)}` : ''].filter(Boolean).join(' · ');
    return h('tr' + (equippable && !on ? '.dim' : ''),
      h('td', h('a', { href: '#', onclick: e => { e.preventDefault(); showItem(it); } }, it.name), it._custom ? h('span.tag.custom', ' custom') : '', sub ? h('div.hint', sub) : null),
      h('td.hint', SR.itemStats(it)), h('td.nowrap', qtyCell), h('td.right.nowrap', btns));
  }
  async function reloadWeapon(it) {
    const stacks = c().inventory.filter(x => x.ammo_for && x.ammo_for === it.ammo_class && x.qty > 0);
    if (!stacks.length) { toast(`You have no ${it.ammo_class || ''} ammunition. Buy some in the store.`, 4000); return; }
    let pick = stacks[0].uid;
    if (stacks.length > 1) {
      const sel = h('select', stacks.map(s => option(s.uid, `${s.name} (${s.qty})`)));
      if (!await UI.modal(`Reload ${it.name}`, h('label.stack', 'Ammunition', sel), { ok: 'Reload', narrow: true })) return;
      pick = sel.value;
    }
    act('reload', { uid: it.uid, ammo: pick });
  }
  async function sell(it, unit) {
    let qty = it.qty || 1;
    if ((it.unit || it.consumable) && qty > 1) {
      const v = await UI.prompt(`Sell ${it.name}`, `How many? (you have ${qty})`, { type: 'number', value: qty, min: 1, ok: 'Next' });
      if (!v) return; qty = Math.max(1, Math.min(qty, +v));
    }
    const price = Math.floor(unit * qty * S.sheet.sellPct / 100);
    if (!await UI.confirm(`Sell ${qty > 1 ? qty + ' × ' : ''}${it.name} for ${money(price)} (${S.sheet.sellPct}% of the price)?${it.implant ? ' The implant is removed.' : ''}`, { ok: 'Sell' })) return;
    act('sell_item', { uid: it.uid, qty });
  }
  async function editGear(it) {
    const statsLocked = !(cfg.gm || (draft() && it._custom));
    const n = await SR.editItem(it, { statsLocked, title: `Edit ${it.name}` });
    if (n) act('edit_item', { uid: it.uid, item: n });
  }
  function showItem(it) {
    UI.info(it.name, h('div', it.desc ? h('p', it.desc) : null, h('p', SR.itemStats(it) || ''),
      h('dl.kv', [['Category', `${it.cat}${it.sub ? ' · ' + it.sub : ''}`], ['Availability', it.ref ? SR.availText(it.avail, it.legal) : ''], ['Price', money(it.cost || 0) + (it.unit === 'rounds' ? ' per 10' : '')],
        ['Rating', it.rating], ['Grade', it.grade], ['Essence', it.implant ? it.essence : ''], ['Skill', it.skill ? `${it.skill}${it.spec ? ' (' + it.spec + ')' : ''}` : '']]
        .filter(([, v]) => v !== undefined && v !== '' && v !== null).map(([k, v]) => [h('dt', k), h('dd', String(v))]))));
  }
  /* GM: give an item for free, picked from the store or filled in by hand. */
  async function gmGive() {
    let cat = CAT.store.categories[0], chosen = null;
    const cats = h('div.cat-chips');
    const search = h('input', { type: 'search', placeholder: 'Search the whole store…', oninput: () => draw() });
    const list = h('div.pick-list', { style: { maxHeight: '42vh', overflowY: 'auto' } });
    const opts = h('div.row.tight');
    function draw() {
      cats.innerHTML = '';
      for (const k of CAT.store.categories) cats.append(h('button.small' + (k === cat ? '.active' : ''), { type: 'button', onclick: () => { cat = k; chosen = null; draw(); } }, k));
      list.innerHTML = '';
      list.append(h('label.pick', h('div', h('div', h('b', 'Custom item…')), h('div.meta', 'Fill in every field yourself')),
        h('input', { type: 'radio', name: 'give', checked: chosen === 'custom', onchange: () => { chosen = 'custom'; drawOpts(); } })));
      const q = search.value.trim().toLowerCase();
      for (const e of CAT.store.items) {
        if (q ? !JSON.stringify(e).toLowerCase().includes(q) : e.cat !== cat) continue;
        list.append(h('label.pick', h('div', h('div', e.name), h('div.meta', `${e.sub} · ${typeof e.cost === 'number' ? money(e.cost) : e.cost + '¥'} · Avail ${e.avail} · ${SR.itemStats(e)}`)),
          h('input', { type: 'radio', name: 'give', checked: chosen === e, onchange: () => { chosen = e; drawOpts(); } })));
      }
    }
    const rating = h('input', { type: 'number', min: 1, value: 1 }), grade = h('select', Object.keys(CAT.store.grades).map(g => option(g))), qty = h('input', { type: 'number', min: 1, max: 100, value: 1 });
    function drawOpts() {
      opts.innerHTML = '';
      if (!chosen || chosen === 'custom') return;
      if (chosen.rating) { rating.min = chosen.rating[0]; rating.max = chosen.rating[1]; rating.value = chosen.rating[0]; opts.append(h('label', `Rating (${chosen.rating[0]}-${chosen.rating[1]})`, rating)); }
      if (chosen.implant) opts.append(h('label', 'Grade', grade));
      if (!chosen.implant) opts.append(h('label', chosen.sub === 'Ammunition' ? 'Boxes of 10' : 'Quantity', qty));
    }
    draw();
    const ok = await UI.modal('Give an item', h('div',
      h('p.hint', `Free for ${S.sheet.player.name}: no nuyen is taken and no contact is needed.`),
      cats, h('div.mt', search), h('div.mt', list), h('div.mt', opts)), { ok: 'Give', wide: true });
    if (!ok || !chosen) return;
    if (chosen === 'custom') {
      const it = await SR.editItem({}, { title: 'Custom item', ok: 'Give', cat });
      if (it) act('give', { item: it });
    } else act('give', { ref: chosen.id, rating: +rating.value, grade: grade.value, qty: +qty.value });
  }

  // ------------------------------------------------------------ combat
  function combat() {
    const ch = c(), dv = d(), out = h('div');
    const cm = { p: dv.physical_damage, pm: dv.physical_boxes, s: dv.stun_damage, sm: dv.stun_boxes, ov: dv.overflow_boxes };
    const setDmg = (track, value) => act('set_damage', { track, value }, { quiet: true });
    const mon = h('div.card', h('h3', 'Condition monitors', h('span.row.tight', SR.healthTag(dv.status), dv.wound_modifier ? h('span.tag.status-Wounded', `Wounds ${dv.wound_modifier} dice`) : null)),
      h('div.grid2', SR.monitor('physical', cm, { onSet: setDmg }), SR.monitor('stun', cm, { onSet: setDmg })),
      h('p.hint.mt', `Every 3 boxes is −1 die. Stun beyond the track becomes Physical; Physical beyond the track fills ${dv.overflow_boxes} overflow boxes (Body × 2), and the last one is death.` +
        (ch.drain_stun || ch.drain_phys ? ` ${ch.drain_stun + ch.drain_phys} box(es) are drain, which only rest heals.` : '')));
    out.append(mon);
    out.append(healCard());
    const st = Object.keys(dv.statuses || {}).length || cfg.gm ? h('div.card', h('h3', 'Statuses'),
      SR.statusChips(dv.statuses, cfg.gm ? { onRemove: n => act('set_status', { status: n, on: false }, { quiet: true }) } : {}) || h('p.hint', 'None.'),
      cfg.gm ? h('div.row.tight.mt', (() => { const sel = h('select', Object.keys(CAT.statuses).map(s => option(s, `${CAT.statuses[s].icon} ${s}`))); const val = h('input', { type: 'number', min: 1, max: 20, value: 1, style: { width: '4rem' } });
        return [sel, val, h('button.small', { type: 'button', onclick: () => act('set_status', { status: sel.value, on: true, value: +val.value }, { quiet: true }) }, 'Add status')]; })()) :
        h('p.hint', 'Statuses are set by the GM.')) : null;
    const edgeCard = h('div.card', h('h3', 'Edge', h('span.row.tight', SR.pips(ch.current_edge, dv.edge_max), h('b', `${ch.current_edge} / ${dv.edge_max}`))),
      h('p.hint', cfg.gm ? 'Refresh or award Edge from the game page, or set it with “Set Karma / Nuyen / Edge”.' :
        'Your GM refreshes and awards Edge (max 7). Spend it on a roll (after rolling) or here:'),
      !cfg.gm ? h('button', { type: 'button', disabled: !ch.current_edge, onclick: () => SR.edgeMenu(S.sheet, cfg.post, () => reload()) }, 'Spend Edge…') : null);
    const der = h('div.card', h('h3', 'Combat values'), h('div.stats', stat('Initiative', `${dv.initiative_score} + ${dv.initiative_dice}D6`),
      stat('Major + Minor', `1 + ${dv.minor_actions}`, '', 'Actions each round: 1 Major plus Minor actions (1 + 1 per Initiative Die, max 5)'), stat('Defense Rating', dv.defense_rating, '', `Body ${dv.attributes.Body} + armor ${dv.armor}`),
      stat('Defense test', dv.attributes.Reaction + dv.attributes.Intuition, '', 'Reaction + Intuition'), stat('Soak', (S.sheet.pools.find(p => p.key === 'soak') || {}).value, '', 'Body (+ bone lacing etc.)'),
      stat('Unarmed', `${dv.unarmed.dv}${dv.unarmed.type}`, ` · AR ${dv.unarmed.ar}`)));
    out.append(h('div.grid2', edgeCard, der));
    if (st) out.append(st);
    const weapons = S.sheet.pools.filter(p => p.weapon);
    if (weapons.length) {
      const t = h('table.list', h('thead', h('tr', h('th', 'Weapon'), h('th', 'Pool'), ...SR.RANGES.map(r => h('th', { title: CAT.store.rangeMeters[r] }, r.slice(0, 3))), h('th', 'DV'), h('th', 'Modes'), h('th', 'Ammo'))));
      const tb = h('tbody');
      for (const p of weapons) tb.append(h('tr', h('td', p.label), h('td', { title: SR.breakdown(p.parts) }, h('b', p.value)), ...(p.ar || []).map(a => h('td', a == null ? '—' : a)),
        h('td', p.dv + (p.element ? ` ${p.element}` : '')), h('td', (p.modes || []).join('/')), h('td', p.clip ? `${p.loaded}/${p.clip}` : p.consumable ? `×${p.qty}` : '')));
      t.append(tb);
      out.append(h('div.card', h('h3', 'Weapons'), h('div.table-wrap', t), h('p.hint', 'Attack Ratings per range before the firing mode (SA −2, BF −4, FA −6). Compare with the target’s Defense Rating: 4 or more ahead earns Edge (your GM decides).')));
    }
    if (!cfg.gm && cfg.post) {
      if (!rollerEl) rollerEl = SR.roller({ getSheet: () => S.sheet, post: cfg.post, onRolled: res => { if (res.me) mergeMe(res.me); if (cfg.onRolled) cfg.onRolled(res); else if (res.sheet) set(res.sheet); } });
      const logEl = h('div.log', { style: { maxHeight: '420px' } });
      out.append(h('div.grid2', h('div.card', h('h3', 'Dice roller'), rollerEl), h('div.card', h('h3', 'Table log'), logEl)));
      rollerEl.render();
      if (cfg.log) SR.renderLog(logEl, cfg.log());
      S.logEl = logEl;
    }
    return out;
  }
  function healCard() {
    const ch = c(), dv = d(), used = ch.heal_used || {};
    const hurt = dv.physical_damage || dv.stun_damage;
    const card = h('div.card', h('h3', 'Healing'));
    const allies = S.sheet.allies || [];
    const target = h('select', option(S.sheet.player.id, cfg.gm ? S.sheet.player.name : 'Myself'), cfg.gm ? null : allies.map(a => option(a.id, a.name)));
    const healer = cfg.gm ? h('select', option('', 'GM (no healer)'), option(S.sheet.player.id, S.sheet.player.name), allies.map(a => option(a.id, a.name))) : null;
    const assisted = h('input', { type: 'checkbox' });
    const heal = async method => {
      try {
        if (cfg.gm) { const sh = await api(`/api/players/${S.sheet.player.id}/heal`, 'POST', { method, healer: healer.value, assisted: assisted.checked }); set(sh); toast(sh.message, 4000); }
        else { const res = await cfg.post('heal', { method, target: target.value, assisted: assisted.checked }); toast(res.message, 4500); if (res.sheet) set(res.sheet); if (cfg.onRolled) cfg.onRolled(res); }
      } catch (e) { toast(e.message, 4000); }
    };
    const hasKit = ch.inventory.some(it => it.medkit), knowsHeal = (ch.spells || []).some(s => /Heal/.test(s.name));
    card.append(h('div.form-grid', cfg.gm ? h('label', 'Healer', healer) : h('label', 'Patient', target)),
      h('div.row.mt',
        h('button', { type: 'button', disabled: !!used.first_aid && !cfg.gm, onclick: () => heal('first_aid'), title: 'Biotech + Logic vs 5 − Essence; within a minute of the fight' }, 'First aid' + (used.first_aid ? ' ✓' : '')),
        h('button', { type: 'button', disabled: (!hasKit && !cfg.gm) || (!!used.medkit && !cfg.gm), onclick: () => heal('medkit'), title: hasKit ? 'Within an hour; uses supplies' : 'You need a medkit' }, 'Medkit' + (used.medkit ? ' ✓' : '')),
        knowsHeal || cfg.gm ? h('button', { type: 'button', disabled: !!used.magic && !cfg.gm, onclick: () => heal('magic') }, 'Heal spell' + (used.magic ? ' ✓' : '')) : null),
      h('div.row.mt', h('button', { type: 'button', disabled: !dv.stun_damage, onclick: () => heal('natural_stun') }, 'Rest 1 hour (Stun)'),
        h('button', { type: 'button', disabled: !dv.physical_damage, onclick: () => heal('natural_physical') }, 'Rest 1 day (Physical)'),
        h('label.check', assisted, 'A Biotech-trained helper watches (+2)')),
      h('p.hint', hurt ? 'First aid, medkit and magic each work once per set of injuries (✓ = used; resets when you take new damage) and never heal drain. Rest heals everything over time.' :
        'Not hurt.'));
    return card;
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
    card.append(h('p.hint', `Contacts get you gear: a contact who covers a kind of goods can find items whose Availability is lower than their Connection. Legal items up to Availability ${CAT.store.alwaysAvail} are always on sale.` +
      (S.sheet.approved && !cfg.gm ? ' New contacts and changes to Connection, Loyalty or what they sell must be confirmed by your GM.' : '')));
    if (!ch.contacts.length) { card.append(h('p.hint', 'Fixers, fences, street docs… add the people your runner can call.')); return card; }
    const t = h('table.list', h('thead', h('tr', h('th', 'Name'), h('th', 'Type'), h('th', 'Connection'), h('th', 'Loyalty'), h('th', 'Sources'), h('th', ''))));
    const tb = h('tbody');
    ch.contacts.forEach((ct, i) => tb.append(h('tr.clickable', { onclick: e => { if (!e.target.closest('button')) editContact(i); }, title: ct.notes || '' },
      h('td', h('b', ct.name), ct.verified === false ? h('span.tag.waiting', { style: { marginLeft: '.4rem' } }, 'Waiting for GM') : null),
      h('td', ct.type), h('td', ct.connection), h('td', ct.loyalty),
      h('td', (() => { const sup = SR.contactSupply(ct); return sup.length ? h('div.chips-list', sup.map(s => h('span.chip.small', s === 'Fixer' ? 'Anything' : s))) : h('span.hint', 'Nothing (tick what they can source)'); })()),
      h('td.right.nowrap', cfg.gm && ct.verified === false ? h('button.small.primary', { type: 'button', onclick: () => act('verify_contact', { index: i, verified: true }) }, 'Confirm') : null,
        h('button.small.danger', { type: 'button', onclick: async () => { if (await UI.confirm(`Remove ${ct.name}?`, { danger: true, ok: 'Remove' })) act('remove_contact', { index: i }); } }, '✕')))));
    t.append(tb);
    card.append(h('div.table-wrap', t));
    return card;
  }
  async function editContact(i) {
    const ct = i === null ? { connection: 1, loyalty: 1, supply: [] } : c().contacts[i];
    const name = h('input', { value: ct.name || '', required: true });
    const type = h('select', CAT.contactTypes.map(x => option(x, x, x === ct.type)));
    if (ct.type && !CAT.contactTypes.includes(ct.type)) type.prepend(option(ct.type, ct.type, true));
    const conn = h('input', { type: 'number', min: 1, max: 12, value: ct.connection || 1 });
    const loyal = h('input', { type: 'number', min: 1, max: 12, value: ct.loyalty || 1 });
    const typeSup = () => CAT.contactTypeSupply[type.value] || [];
    const boxes = CAT.store.supply.map(s => h('label.check', h('input', { type: 'checkbox', value: s, checked: (ct.supply || []).includes(s) }), s === 'Fixer' ? 'Anything (fixer)' : s));
    const fromType = h('p.hint');
    const syncType = () => {
      const ts = typeSup();
      for (const b of boxes) { const x = b.querySelector('input'); const t = ts.includes(x.value); x.disabled = t; if (t) x.checked = true; else if (x.dataset.auto) x.checked = false; x.dataset.auto = t ? '1' : ''; }
      fromType.textContent = ts.length ? `A ${type.value.toLowerCase()} sources ${ts.includes('Fixer') ? 'anything' : ts.join(', ')}. Tick more if they have other connections.` : 'Tick what this contact can source.';
    };
    type.onchange = syncType; syncType();
    const notes = h('textarea', { rows: 4 }, ct.notes || '');
    const ok = await UI.modal(i === null ? 'New contact' : `Edit ${ct.name}`, h('div',
      h('div.form-grid', h('label', 'Name', name), h('label', 'Type', type), h('label', 'Connection (1-12)', conn), h('label', 'Loyalty (1-12)', loyal)),
      h('h4.mt', 'Can source'), fromType, h('div.check-grid', boxes), h('label.stack', 'Notes', notes)), { ok: 'Save' });
    if (!ok) return;
    const supply = boxes.map(b => b.querySelector('input')).filter(x => x.checked && !x.disabled).map(x => x.value);
    act('save_contact', { index: i, contact: { name: name.value, type: type.value, connection: +conn.value, loyalty: +loyal.value, supply, notes: notes.value, verified: true } });
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
    load, reload, render, go, act,
    setSheet: sh => set(sh),
    get: () => S.sheet,
    editing,
    updateLog(rolls) { if (S.logEl && S.logEl.isConnected) SR.renderLog(S.logEl, rolls); },
    mergeMe,
  };
}
return { mount };
})();
