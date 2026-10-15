/*
 * v1.55.0 — split editors and a collapsible / resizable project column (Ansible, Terraform).
 *
 *   HiSplit.editors(o)  -> api      1–4 editor panes side by side (2x2 for 4)
 *   HiSplit.sidebar(workEl, key)    − / + on the project card, drag the gap to resize it
 *
 * How the panes share one page's code: the page's own functions use fixed element ids
 * (e.g. 'tf-ed', 'tf-edname', 'tf-dirty', 'tf-save') and two variables (the open file and its
 * "unsaved" flag). The ACTIVE pane owns those ids; the other panes keep their elements under
 * suffixed ids and their own {path, dirty}. Focusing or clicking a pane makes it active
 * (ids swapped, variables swapped), so open / save / copy / format / validate work on the pane
 * you are in without changing the page code. Events typed in a pane are passed to the first
 * pane's textarea, where the page's listeners live.
 *
 *   o = { prefix, card, ids: ['ed','edname','edtype','dirty','save','copyfile'],
 *         get: () => ({path, dirty}), set: (s) => {}, save: async () => {}, open: async (path) => {},
 *         clear: () => {}, attach: {HiEd.attach options}, storeKey }
 */
(function () {
  'use strict';
  const LS = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };

  function editors(o) {
    const P = o.prefix, ids = o.ids.map((n) => P + '-' + n);
    const col = document.createElement('div');        // [View: 1 2 3 4] above the panes, one grid cell
    col.className = 'split-col';
    o.card.parentNode.insertBefore(col, o.card);
    const grid = document.createElement('div');
    grid.className = 'split-grid';
    col.appendChild(grid);
    grid.appendChild(o.card);
    const bar = document.createElement('div');
    bar.className = 'split-bar';
    bar.innerHTML = '<span>View:</span>' + [1, 2, 3, 4].map((n) =>
      '<button type="button" data-n="' + n + '" title="' + n + ' editor' + (n > 1 ? 's' : '') + ' side by side' + (n === 4 ? ' (2 x 2)' : '') + '">' +
      ['▭', '◫', '▥', '⊞'][n - 1] + ' ' + n + '</button>').join('') +
      '<span class="split-hint">click a pane, then a file in the tree to open it there</span>';
    col.insertBefore(bar, grid);

    const orig = {};                                   // pane 0's elements (they keep the page's listeners)
    ids.forEach((id) => { orig[id] = document.getElementById(id); });
    const headTpl = o.card.querySelector('.ans-edhead').cloneNode(true);
    const taTpl = orig[P + '-ed'];
    const panes = [{ card: o.card, els: Object.assign({}, orig), state: { path: '', dirty: false } }];
    let act = 0;
    function wireCm(cm, k) {                           // typing / clicking in a pane makes it active first
      cm.on('focus', () => activate(k));
      cm.on('beforeChange', (c, ch) => { if (ch.origin && ch.origin !== 'setValue') activate(k); });
    }
    if (window.HiEd && HiEd.cmOf(orig[P + '-ed'])) wireCm(HiEd.cmOf(orig[P + '-ed']), 0);
    o.card.addEventListener('mousedown', () => activate(0), true);

    function own(k) {                                  // pane k takes the page's ids
      panes.forEach((p, i) => ids.forEach((id) => { if (p.els[id]) p.els[id].id = i === k ? id : id + '__p' + i; }));
    }
    function activate(k, quiet) {
      if (k === act || !panes[k]) return;
      panes[act].state = o.get();
      act = k;
      own(k);
      o.set(panes[k].state, quiet);
      panes.forEach((p, i) => p.card.classList.toggle('split-act', i === k && panes.length > 1));
      if (o.onActivate) o.onActivate(k);
    }
    function bridge(k, ta) {                           // pane k's typing -> the page's listeners
      const first = orig[P + '-ed'];
      ta.addEventListener('input', () => { if (act !== k) activate(k); first.dispatchEvent(new Event('input')); });
      ta.addEventListener('keydown', (e) => {
        if (act !== k) activate(k);
        const ev = new KeyboardEvent('keydown', { key: e.key, code: e.code, ctrlKey: e.ctrlKey, metaKey: e.metaKey,
                                                   shiftKey: e.shiftKey, altKey: e.altKey, bubbles: true, cancelable: true });
        first.dispatchEvent(ev);
        if (ev.defaultPrevented) e.preventDefault();
      });
    }
    function addPane() {
      const k = panes.length;
      const card = document.createElement('div');
      card.className = o.card.className;
      const head = headTpl.cloneNode(true);
      const els = {};
      ids.forEach((id) => {
        const el = head.querySelector('#' + CSS.escape(id));
        if (el) { el.id = id + '__p' + k; els[id] = el; }
      });
      head.querySelectorAll('[id]').forEach((el) => { if (!els[el.id.replace(/__p\d+$/, '')]) el.removeAttribute('id'); });
      const ta = document.createElement('textarea');
      ['class', 'spellcheck', 'placeholder'].forEach((a) => { if (taTpl.getAttribute(a) != null) ta.setAttribute(a, taTpl.getAttribute(a)); });
      ta.id = P + '-ed__p' + k;
      ta.disabled = true;
      card.appendChild(head); card.appendChild(ta);
      grid.appendChild(card);
      els[P + '-ed'] = ta;
      const nm = els[P + '-edname']; if (nm) nm.textContent = '(no file)';
      const ty = els[P + '-edtype']; if (ty) ty.textContent = '';
      const dt = els[P + '-dirty']; if (dt) dt.style.display = 'none';
      if (window.HiEd) {
        const cm = HiEd.attach(ta, Object.assign({}, o.attach));
        if (cm) wireCm(cm, k);
      }
      bridge(k, ta);
      // header buttons: act on this pane through pane 0's handlers
      [P + '-save', P + '-copyfile'].forEach((id) => {
        if (els[id]) els[id].onclick = () => { activate(k); orig[id].click(); };
      });
      card.addEventListener('mousedown', () => activate(k), true);
      panes.push({ card, els, state: { path: '', dirty: false } });
      return k;
    }
    async function setCount(n) {
      n = Math.max(1, Math.min(4, n | 0));
      if (n < panes.length) {
        const gone = panes.slice(n);
        const dirtyGone = gone.some((p, i) => (n + i === act ? o.get().dirty : p.state.dirty));
        if (dirtyGone && !confirm('A pane you are closing has unsaved changes — close it anyway?')) { paint(); return; }
        if (act >= n) activate(0);
        gone.forEach((p) => p.card.remove());
        panes.length = n;
      }
      while (panes.length < n) addPane();
      grid.dataset.n = String(n);
      panes.forEach((p, i) => p.card.classList.toggle('split-act', i === act && n > 1));
      LS(o.storeKey, String(n));
      paint();
      setTimeout(() => panes.forEach((p) => { const cm = window.HiEd && HiEd.cmOf(p.els[P + '-ed']); if (cm) cm.refresh(); }), 30);
    }
    function paint() {
      bar.querySelectorAll('button').forEach((b) => b.classList.toggle('on', +b.dataset.n === panes.length));
    }
    bar.addEventListener('click', (e) => { const b = e.target.closest('button[data-n]'); if (b) setCount(+b.dataset.n); });

    function stateOf(k) { return k === act ? o.get() : panes[k].state; }
    function quietly(fn) {                              // loops over panes: one tree refresh at the end
      const back = act;
      try { return fn(); } finally { if (act !== back) activate(back, true); o.set(o.get(), false); }
    }
    const api = {
      act: () => act,
      activate,
      run(k, fn) {                                      // fn with pane k active (async results land in their own pane)
        const back = act;
        if (k === back) return fn();
        activate(k, true);
        try { return fn(); } finally { activate(back, true); }
      },
      count: () => panes.length,
      paneWith: (path) => panes.findIndex((p, i) => path && stateOf(i).path === path && (!o.proj || stateOf(i).proj === o.proj())),
      anyDirty: () => panes.some((p, i) => stateOf(i).dirty),
      async saveAll() {                                 // before a run: every pane with unsaved changes
        const back = act;
        for (let k = 0; k < panes.length; k++) {
          if (!stateOf(k).dirty) continue;
          activate(k, true);
          if (!confirm(o.get().path + ' has unsaved changes — save before running?')) continue;
          if ((await o.save(true)) === false) { activate(back); return false; }
        }
        activate(back, true);
        o.set(o.get(), false);
        return true;
      },
      async reloadAll() {                               // after a run that may rewrite files (fmt)
        for (let k = 0; k < panes.length; k++) {
          const s = stateOf(k);
          if (!s.path || s.dirty || panes[k].card.contains(document.activeElement)) continue;   // not under the cursor
          const back = act;
          activate(k, true);
          const pr = o.open(s.path);                    // openFile applies its result to pane k itself
          activate(back, true);
          await pr;
        }
      },
      clearAll() { quietly(() => { for (let k = 0; k < panes.length; k++) { activate(k, true); o.clear(); } }); },
      forget(path) {                                    // a file / folder was deleted
        quietly(() => {
          for (let k = 0; k < panes.length; k++) {
            const s = stateOf(k);
            if (s.path && (s.path === path || s.path.startsWith(path + '/'))) { activate(k, true); o.clear(); }
          }
        });
      },
    };
    setCount(+(LS(o.storeKey) || 1));
    return api;
  }

  // ------------------------------------------------------------------ project column: − / +, drag to resize
  function sidebar(work, key, title) {
    const side = work.children[0];
    const handle = document.createElement('div');
    handle.className = 'split-handle';
    handle.title = 'drag to resize';
    work.insertBefore(handle, work.children[1]);
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'split-collapse';
    const h = side.querySelector('.ans-h');
    h.insertBefore(btn, h.firstChild);
    let w = +(LS(key + '.w') || 290), col = LS(key + '.c') === '1';
    function apply() {
      work.style.gridTemplateColumns = (col ? '34px' : w + 'px') + ' 8px minmax(0, 1fr)';
      side.classList.toggle('split-collapsed', col);
      btn.textContent = col ? '+' : '−';
      btn.title = col ? 'Show the ' + title + ' panel' : 'Hide the ' + title + ' panel';
      handle.style.visibility = col ? 'hidden' : '';
      setTimeout(() => window.dispatchEvent(new Event('resize')), 30);
    }
    btn.onclick = (e) => { e.stopPropagation(); col = !col; LS(key + '.c', col ? '1' : '0'); apply(); };
    handle.addEventListener('mousedown', (e) => {
      e.preventDefault();
      const x0 = e.clientX, w0 = w;
      const mv = (ev) => { w = Math.max(180, Math.min(700, w0 + ev.clientX - x0)); apply(); };
      const up = () => { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); LS(key + '.w', String(w)); };
      document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
    });
    apply();
  }

  window.HiSplit = { editors, sidebar };
})();
