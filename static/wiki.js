/* Wiki: the original app's reference tree, searchable. */
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
    for (const cat of wiki.tree) {
      const det = h('details', { open: !!q || cat.title === 'Rules' }, h('summary', cat.title));
      let any = false;
      for (const sub of cat.children) {
        const kids = sub.children.filter(k => match(k.title));
        if (!kids.length && !match(sub.title)) continue;
        any = true;
        if (!sub.children.length) { det.append(leaf(sub.title)); continue; }
        const sd = h('details', { open: !!q }, h('summary', h('span', { onclick: () => show(sub.title) }, sub.title)));
        if (wiki.topics[sub.title]) sd.append(leaf(sub.title));
        kids.forEach(k => sd.append(leaf(k.title)));
        det.append(sd);
      }
      if (any) list.append(det);
    }
    tree.querySelectorAll('.leaf').forEach(b => b.classList.toggle('active', b.dataset.t === current));
  }
  search.oninput = draw;
  draw(); show(current);
};
