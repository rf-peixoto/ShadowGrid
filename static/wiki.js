/* Wiki: the rules and catalog reference tree (any depth), searchable. */
window.Wiki = function Wiki(root, wiki) {
  const tree = h('div.wiki-tree'), list = h('div'), body = h('article.wiki-body');
  const search = h('input', { type: 'search', placeholder: 'Search the wiki…', 'aria-label': 'Search the wiki' });
  let current = 'Edge';
  tree.append(search, list);
  root.append(tree, body);
  function show(title) {
    current = title;
    body.innerHTML = '';
    body.append(renderWiki(wiki.topics[title] || `**${title}**\n\nNo information available for this topic.`));
    tree.querySelectorAll('.leaf').forEach(b => b.classList.toggle('active', b.dataset.t === title));
  }
  function leaf(t) { return h('button.leaf', { type: 'button', dataset: { t }, onclick: () => show(t) }, t); }
  function draw() {
    const q = search.value.trim().toLowerCase();
    list.innerHTML = '';
    const match = t => !q || t.toLowerCase().includes(q) || (wiki.topics[t] || '').toLowerCase().includes(q);
    // any depth: a node with children is a folder (clicking its name opens its own topic, if it has one)
    function node(n, top) {
      const kids = (n.children || []).map(k => node(k, false)).filter(Boolean);
      if (!(n.children || []).length) return match(n.title) ? leaf(n.title) : null;
      if (!kids.length && !(q && match(n.title))) return null;
      const d = h('details', { open: !!q || (top && n.title === 'Rules') },
        h('summary', top ? n.title : h('span', { onclick: () => { if (wiki.topics[n.title]) show(n.title); } }, n.title)));
      if (!top && wiki.topics[n.title]) d.append(leaf(n.title));
      d.append(...kids);
      return d;
    }
    for (const cat of wiki.tree) { const el = node(cat, true); if (el) list.append(el); }
    tree.querySelectorAll('.leaf').forEach(b => b.classList.toggle('active', b.dataset.t === current));
  }
  search.oninput = draw;
  draw(); show(current);
};
