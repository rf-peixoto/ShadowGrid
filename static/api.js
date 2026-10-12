/* Shared client helpers: JSON API with CSRF header, toasts, DOM builder, dialogs. */
// append()/prepend() skip null, undefined and false, like h() does, so optional parts never print "null".
(() => {
  for (const proto of [Element.prototype, DocumentFragment.prototype]) {
    for (const name of ['append', 'prepend']) {
      const orig = proto[name];
      proto[name] = function (...nodes) { return orig.apply(this, nodes.filter(n => n !== null && n !== undefined && n !== false)); };
    }
  }
})();
window.api = async function api(path, method = 'GET', body) {
  const res = await fetch(path, {
    method, headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'ShadowGrid' },
    body: body === undefined ? undefined : (typeof body === 'string' ? body : JSON.stringify(body)),
  });
  if (res.status === 401) { location.href = '/login?next=' + encodeURIComponent(location.pathname); throw new Error('auth'); }
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) throw new Error((data && data.error) || res.statusText);
  return data;
};
window.toast = function toast(msg, ms = 2600) {
  let el = document.getElementById('toast');
  if (!el) { el = document.createElement('div'); el.id = 'toast'; el.setAttribute('role', 'status'); document.body.appendChild(el); }
  el.textContent = msg; el.classList.add('show');
  clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove('show'), ms);
};
window.escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* h('div.card#id', {onclick, title, ...}, child, 'text', [children]) */
window.h = function h(sel, attrs, ...kids) {
  const m = /^([a-z0-9]+)?((?:[.#][\w-]+)*)$/i.exec(sel) || [];
  const el = document.createElement(m[1] || 'div');
  for (const part of (m[2] || '').match(/[.#][\w-]+/g) || []) {
    if (part[0] === '.') el.classList.add(part.slice(1)); else el.id = part.slice(1);
  }
  if (attrs !== null && attrs !== undefined && (typeof attrs !== 'object' || attrs instanceof Node || Array.isArray(attrs))) { kids.unshift(attrs); attrs = null; }
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'class') el.className += ' ' + v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (['value', 'checked', 'disabled', 'selected', 'hidden', 'open', 'textContent', 'innerHTML'].includes(k)) el[k] = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  const add = c => { if (c === null || c === undefined || c === false) return; if (Array.isArray(c)) c.forEach(add); else el.append(c instanceof Node ? c : document.createTextNode(String(c))); };
  kids.forEach(add);
  return el;
};
window.money = n => `${Math.round(Number(n) || 0).toLocaleString('en-US')}¥`;
window.timeAgo = t => {
  const s = Math.max(0, Date.now() / 1000 - t);
  if (s < 60) return 'just now'; if (s < 3600) return Math.floor(s / 60) + ' min ago';
  if (s < 86400) return Math.floor(s / 3600) + ' h ago'; return new Date(t * 1000).toLocaleDateString();
};
window.option = (value, label, selected) => h('option', { value, selected: !!selected }, label ?? value);

/* Promise-based modal dialogs built on <dialog>. */
window.UI = (() => {
  function modal(title, body, { ok = 'Save', cancel = 'Cancel', danger = false, wide = false, narrow = false, onOpen } = {}) {
    return new Promise(resolve => {
      const d = h('dialog', { class: wide ? 'wide' : narrow ? 'narrow' : '' });
      const form = h('form', { method: 'dialog' });
      form.append(h('h2', title), body);
      const okBtn = ok ? h('button', { value: 'ok', class: danger ? 'danger primary' : 'primary' }, ok) : null;
      form.append(h('div.row.end', cancel ? h('button', { value: 'cancel', type: 'button', onclick: () => d.close('cancel') }, cancel) : null, okBtn));
      d.append(form); document.body.append(d);
      form.addEventListener('submit', e => {
        if (e.submitter && e.submitter.value === 'ok' && !form.checkValidity()) { e.preventDefault(); form.reportValidity(); }
      });
      d.addEventListener('close', () => { resolve(d.returnValue === 'ok'); setTimeout(() => d.remove(), 0); });
      d.showModal();
      if (onOpen) onOpen(d);
      const first = body.querySelector && body.querySelector('input:not([type=hidden]):not([type=checkbox]), select, textarea');
      if (first) first.focus();
    });
  }
  const confirm = (text, opts = {}) => modal(opts.title || 'Are you sure?', h('p', text), { ok: opts.ok || 'Confirm', danger: opts.danger, narrow: true });
  async function prompt(title, label, { value = '', type = 'text', ok = 'OK', hint = '', min, required = true } = {}) {
    const inp = h('input', { type, value, min, required });
    const okd = await modal(title, h('div', h('label.stack', label, inp), hint ? h('p.hint', hint) : null), { ok, narrow: true });
    return okd ? inp.value : null;
  }
  function info(title, content) { return modal(title, content, { ok: 'Close', cancel: null, narrow: true }); }
  return { modal, confirm, prompt, info };
})();

/* Tiny Markdown-ish renderer for wiki topics (**bold** lines become headings, "- " lines become lists). */
window.renderWiki = function renderWiki(text) {
  const out = h('div');
  let list = null;
  for (const raw of String(text || '').split('\n')) {
    const line = raw.trimEnd();
    if (/^\*\*(.+)\*\*$/.test(line)) { list = null; out.append(h(out.childNodes.length ? 'h3' : 'h2', line.slice(2, -2))); continue; }
    if (line.startsWith('- ')) { if (!list) { list = h('ul'); out.append(list); } list.append(h('li', line.slice(2))); continue; }
    list = null;
    if (line.trim()) out.append(h('p', line));
  }
  return out;
};

/* Live updates: one server-sent-events stream per page. Live.on(fn) calls fn (debounced) whenever
   something changed on the server; pages keep a slow poll as a safety net. */
window.Live = (() => {
  const subs = [];
  let es = null, timer = null, fails = 0;
  const fire = () => { clearTimeout(timer); timer = setTimeout(() => subs.forEach(fn => { try { fn(); } catch (e) { console.error(e); } }), 60); };
  function connect() {
    if (es || typeof EventSource === 'undefined') return;
    es = new EventSource('/api/events');
    es.addEventListener('hello', () => { fire(); fails = 0; });   // catch anything written before the stream was open
    es.addEventListener('change', fire);
    es.onerror = () => { fails++; if (es.readyState === EventSource.CLOSED) { es = null; setTimeout(connect, Math.min(30000, 2000 * fails)); } };
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) fire(); });
  return { on(fn) { subs.push(fn); connect(); }, connected: () => !!es && es.readyState === 1 };
})();

/* Safe Markdown for handouts and session notes: headings (#), **bold**, *italic*, `code`, [links](https://…),
   lists (- or 1.), > quotes, --- rules and paragraphs. Builds DOM nodes only; HTML in the text stays text. */
window.renderMarkdown = function renderMarkdown(text) {
  const out = h('div.md');
  const inline = s => {
    const frag = document.createDocumentFragment();
    const re = /(\*\*([^*]+)\*\*|__([^_]+)__|\*([^*\s][^*]*)\*|_([^_\s][^_]*)_|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\))/g;
    let last = 0, m;
    while ((m = re.exec(s))) {
      if (m.index > last) frag.append(s.slice(last, m.index));
      if (m[2] || m[3]) frag.append(h('strong', m[2] || m[3]));
      else if (m[4] || m[5]) frag.append(h('em', m[4] || m[5]));
      else if (m[6]) frag.append(h('code', m[6]));
      else if (m[7]) frag.append(h('a', { href: m[8], target: '_blank', rel: 'noopener noreferrer nofollow' }, m[7]));
      last = re.lastIndex;
    }
    if (last < s.length) frag.append(s.slice(last));
    return frag;
  };
  const lines = String(text || '').replace(/\r\n?/g, '\n').split('\n');
  let para = [], list = null, quote = null;
  const flush = () => {
    if (para.length) { const p = h('p'); para.forEach((l, i) => { if (i) p.append(h('br')); p.append(inline(l)); }); (quote || out).append(p); para = []; }
  };
  for (const raw of lines) {
    const line = raw.replace(/\s+$/, '');
    let m;
    if (!line.trim()) { flush(); list = null; quote = null; continue; }
    if ((m = /^(#{1,3})\s+(.*)$/.exec(line))) { flush(); list = null; quote = null; out.append(h('h' + (m[1].length + 2), inline(m[2]))); continue; }
    if (/^(-{3,}|\*{3,})$/.test(line.trim())) { flush(); list = null; quote = null; out.append(h('hr')); continue; }
    if ((m = /^>\s?(.*)$/.exec(line))) { if (!quote) { flush(); list = null; quote = h('blockquote'); out.append(quote); } para.push(m[1]); continue; }
    if ((m = /^\s*([-*+]|\d+[.)])\s+(.*)$/.exec(line))) {
      flush(); quote = null;
      const ordered = /\d/.test(m[1]);
      if (!list || (list.tagName === 'OL') !== ordered) { list = h(ordered ? 'ol' : 'ul'); out.append(list); }
      list.append(h('li', inline(m[2]))); continue;
    }
    if (list && /^\s{2,}/.test(raw)) { list.lastChild.append(' ', inline(line.trim())); continue; }
    list = null;
    if (quote) { flush(); quote = null; }
    para.push(line);
  }
  flush();
  return out;
};
