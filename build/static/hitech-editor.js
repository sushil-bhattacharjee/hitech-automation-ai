/*
 * v1.54.0 — code checks in every editor (hiTech Automation AI).
 *
 *   HiEd.attach(textarea, {lang, height, files, hcl})  -> CodeMirror instance
 *   HiEd.enhance(cm, {lang, files})                     -> adds checks to an existing CodeMirror
 *   HiEd.setLang(textareaOrCm, lang)                    'json' 'xml' 'yaml' 'ansible' 'python' 'hcl' 'jinja' 'payload' 'text'
 *   HiEd.langFor(filename)
 *   HiEd.format(textareaOrCm)                           -> Promise<{ok, msg}>   (✨ Format)
 *
 * attach() puts a CodeMirror editor where the textarea was and keeps the textarea as the API:
 * reading or setting textarea.value, .disabled, .focus() and 'input' / 'keydown' listeners keep
 * working, so the page code around each editor does not change.
 *
 * Checks (red/amber underline + gutter marker, message on hover):
 *   json / xml   in the browser; {{ var }} and {% %} placeholders are not errors
 *   yaml         js-yaml (indentation, tabs, duplicate keys, bad mappings) + Ansible's
 *                "value starts with {{ — quote it" rule; !vault / !unsafe tags accepted
 *   python       ruff on the server (/api/python-lint — static only, nothing runs)
 *   hcl          brackets / quotes / heredocs / empty "name =" as you type; terraform
 *                validate is added by the Terraform page on save (HiEd.setExternal)
 *   jinja        {{ }} {% %} {# #} balance and if/for/macro/block … end* pairs
 * Visible: trailing spaces and tab characters. Ctrl-Space (or typing) = suggestions.
 * Everything is vendored under /static — works offline (lab workstations) and on the public site.
 */
(function () {
  'use strict';
  if (!window.CodeMirror) return;                       // assets missing -> plain textareas stay
  const CM = window.CodeMirror;
  const TPL_RE = /\{\{[\s\S]*?\}\}|\{%[\s\S]*?%\}|\{#[\s\S]*?#\}/g;
  const blank = (s) => s.replace(/[^\n]/g, ' ');        // same length, line breaks kept

  // ------------------------------------------------------------------ helpers
  function posFromIndex(text, idx) {
    let line = 0, col = 0;
    for (let i = 0; i < idx && i < text.length; i++) {
      if (text[i] === '\n') { line++; col = 0; } else col++;
    }
    return { line, ch: col };
  }
  let _mt = null, _ml = null;
  function mark(line, ch, msg, severity, text) {
    if (_mt !== text) { _mt = text; _ml = text.split('\n'); }
    const lines = _ml;
    line = Math.max(0, Math.min(line, lines.length - 1));
    const L = lines[line] || '';
    ch = Math.max(0, Math.min(ch, L.length));
    let end = ch + 1;
    if (ch >= L.length) { ch = Math.max(0, L.length - 1); end = L.length || 1; }
    return { from: CM.Pos(line, ch), to: CM.Pos(line, end), message: msg, severity: severity || 'error' };
  }

  // ------------------------------------------------------------------ JSON
  function lintJSON(text) {
    if (!text.trim()) return [];
    const masked = text.replace(TPL_RE, (m) => '0' + blank(m).slice(1));
    try { JSON.parse(masked); return []; } catch (e) {
      const msg = String(e.message || e);
      let p = null, m;
      if ((m = msg.match(/line (\d+) column (\d+)/))) p = { line: +m[1] - 1, ch: +m[2] - 1 };
      else if ((m = msg.match(/position (\d+)/))) p = posFromIndex(masked, +m[1]);
      else if (/end of (JSON )?(data|input)/i.test(msg)) p = posFromIndex(masked, masked.trimEnd().length);
      p = p || { line: 0, ch: 0 };
      return [mark(p.line, p.ch, 'JSON: ' + msg.replace(/^JSON\.parse: /, ''), 'error', text)];
    }
  }

  // ------------------------------------------------------------------ XML
  function lintXML(text) {
    if (!text.trim()) return [];
    let body = text.replace(TPL_RE, blank);
    body = body.replace(/^(\s*)<\?xml[^>]*\?>/, (m) => blank(m));         // declaration -> spaces
    const wrapped = '<r>' + body + '</r>';                                 // several top elements are fine
    const doc = new DOMParser().parseFromString(wrapped, 'application/xml');
    const err = doc.getElementsByTagName('parsererror')[0];
    if (!err) return [];
    const t = err.textContent || '';
    let m = t.match(/line (\d+) at column (\d+)/i) || t.match(/Line Number (\d+), Column (\d+)/i);
    let line = 0, ch = 0;
    if (m) { line = +m[1] - 1; ch = +m[2] - 1; if (line === 0) ch -= 3; }
    const reason = (t.match(/(?:error on line \d+ at column \d+: |XML Parsing Error: )([^\n]+)/i) || [])[1] ||
                   t.replace(/This page contains the following errors:|Below is a rendering[\s\S]*/g, '').trim();
    return [mark(line, Math.max(0, ch), 'XML: ' + reason.replace(/\s+/g, ' ').slice(0, 300), 'error', text)];
  }

  // ------------------------------------------------------------------ YAML (+ Ansible rules)
  let YAML_SCHEMA = null;
  function yamlSchema() {
    if (YAML_SCHEMA || !window.jsyaml) return YAML_SCHEMA;
    const any = (tag) => ['scalar', 'sequence', 'mapping'].map((kind) => new jsyaml.Type(tag, { kind, construct: (d) => d }));
    YAML_SCHEMA = jsyaml.DEFAULT_SCHEMA.extend([].concat(any('!vault'), any('!unsafe'), any('!ref')));
    return YAML_SCHEMA;
  }
  function lintYAML(text, ansible) {
    if (!text.trim() || !window.jsyaml) return [];
    const out = [];
    try { jsyaml.loadAll(text, () => {}, { schema: yamlSchema() }); } catch (e) {
      const mk = e.mark || {};
      out.push(mark(mk.line || 0, mk.column || 0, 'YAML: ' + (e.reason || e.message), 'error', text));
    }
    if (ansible) {
      let block = -1;                                   // indent of a  key: |  /  key: >  line
      text.split('\n').forEach((L, i) => {
        const ind = L.match(/^ */)[0].length;
        if (block >= 0) { if (!L.trim() || ind > block) return; block = -1; }
        if (/(?:^|[:\s-])[|>][-+0-9]*\s*(?:#.*)?$/.test(L) && /:\s*[|>]|^\s*-\s*[|>]/.test(L)) { block = ind; return; }
        // key: {{ var }}   or   - {{ var }}   -> YAML reads it as a dictionary; Ansible needs quotes
        const m = L.match(/^(\s*(?:-\s+)?(?:[\w.-]+:\s+)?)\{\{/);
        if (m && !/^\s*#/.test(L)) {
          out.push({ from: CM.Pos(i, m[1].length), to: CM.Pos(i, L.length),
                     message: 'Ansible: a value that starts with {{ must be quoted — "' + L.slice(m[1].length).trim() + '"',
                     severity: 'error' });
        }
      });
    }
    return out;
  }

  // ------------------------------------------------------------------ Jinja2
  const J_OPEN = { if: 'endif', for: 'endfor', macro: 'endmacro', block: 'endblock', call: 'endcall',
                   filter: 'endfilter', with: 'endwith', autoescape: 'endautoescape', trans: 'endtrans' };
  // end of an expression starting at i (after the opening "{{" / "{%"): nested braces and quotes skipped
  function jinjaEnd(text, i, close) {
    let depth = 0, q = null;
    for (; i < text.length; i++) {
      const c = text[i];
      if (q) { if (c === '\\') i++; else if (c === q) q = null; continue; }
      if (c === '"' || c === "'") { q = c; continue; }
      if (c === '{' || c === '(' || c === '[') { depth++; continue; }
      if ((c === '}' || c === ')' || c === ']') && depth > 0) { depth--; continue; }
      if (depth === 0) {
        if (close === '}}' && text.startsWith('}}', i)) return i;
        if (close === '%}' && /^[-+]?%\}/.test(text.slice(i, i + 3))) return i;
        if (text.startsWith('{{', i) || text.startsWith('{%', i)) return -2;   // next tag before this one closed
      }
    }
    return -1;
  }
  function lintJinja(text) {
    const out = [], stack = [];
    const err = (k, msg) => { const p = posFromIndex(text, k); out.push(mark(p.line, p.ch, 'Jinja: ' + msg, 'error', text)); };
    let i = 0;
    while (i < text.length) {
      const two = text.slice(i, i + 2);
      if (two === '{#') { const e = text.indexOf('#}', i + 2); if (e < 0) { err(i, '"{#" comment is never closed'); break; } i = e + 2; continue; }
      if (two === '{{' || two === '{%') {
        const close = two === '{{' ? '}}' : '%}';
        const e = jinjaEnd(text, i + 2, close);
        if (e < 0) { err(i, '"' + two + '" ' + (e === -2 ? 'is not closed before the next tag' : 'is never closed') + ' (expected "' + close + '")'); i += 2; continue; }
        if (two === '{%') {
          const inner = text.slice(i + 2, e).replace(/^[-+]?\s*/, '');
          const kw = (inner.match(/^(\w+)/) || [])[1];
          const p = posFromIndex(text, i);
          if (kw === 'raw') {                           // nothing inside {% raw %} is Jinja
            const m = /\{%[-+]?\s*endraw\s*[-+]?%\}/g; m.lastIndex = e;
            const r = m.exec(text);
            if (!r) { err(i, '{% raw %} has no {% endraw %}'); break; }
            i = r.index + r[0].length; continue;
          }
          if (kw === 'set' && !/=/.test(inner)) stack.push({ kw: 'set', end: 'endset', p });
          else if (kw && J_OPEN[kw]) stack.push({ kw, end: J_OPEN[kw], p });
          else if (kw && /^end\w+/.test(kw)) {
            const top = stack.pop();
            if (!top) err(i, '{% ' + kw + ' %} without an opening tag');
            else if (top.end !== kw) err(i, '{% ' + kw + ' %} but {% ' + top.kw + ' %} (line ' + (top.p.line + 1) + ') needs {% ' + top.end + ' %}');
          }
          i = e + (text[e] === '%' ? 2 : 3); continue;
        }
        i = e + 2; continue;
      }
      if (/^[-+]?%\}/.test(text.slice(i, i + 3)) && text[i] !== '}') { err(i, '"%}" without an opening "{%"'); i += 2; continue; }
      i++;
    }
    stack.forEach((t) => out.push(mark(t.p.line, t.p.ch, 'Jinja: {% ' + t.kw + ' %} has no {% ' + t.end + ' %}', 'error', text)));
    return out;
  }

  // ------------------------------------------------------------------ HCL (Terraform) — instant checks
  function lintHCL(text) {
    const out = [], stack = [], skip = [];            // [startIndex, endIndex] of heredocs and /* */
    const pairs = { '{': '}', '[': ']', '(': ')' };
    let i = 0, n = text.length;
    const at = (k) => posFromIndex(text, k);
    while (i < n) {
      const c = text[i], c2 = text.slice(i, i + 2);
      if (c === '#' || c2 === '//') { while (i < n && text[i] !== '\n') i++; continue; }
      if (c2 === '/*') { const e = text.indexOf('*/', i + 2); if (e < 0) { const p = at(i); out.push(mark(p.line, p.ch, 'HCL: /* comment is never closed', 'error', text)); break; } skip.push([i, e + 2]); i = e + 2; continue; }
      if (c2 === '<<') {                                   // heredoc  <<EOF / <<-EOF
        const hm = text.slice(i).match(/^<<-?([A-Za-z_]\w*)[ \t]*\n/);
        if (hm) {
          const tag = hm[1], start = i;
          const re = new RegExp('^[ \\t]*' + tag + '[ \\t]*$', 'm');
          const rest = text.slice(i + hm[0].length), em = rest.match(re);
          if (!em) { const p = at(start); out.push(mark(p.line, p.ch, 'HCL: heredoc <<' + tag + ' has no closing ' + tag + ' line', 'error', text)); break; }
          skip.push([i, i + hm[0].length + em.index + em[0].length]);
          i += hm[0].length + em.index + em[0].length; continue;
        }
      }
      if (c === '"') {                                     // string with ${ } / %{ } templates
        const start = i; i++; let depth = 0, closed = false;
        while (i < n) {
          const d = text[i];
          if (d === '\\') { i += 2; continue; }
          if ((d === '$' || d === '%') && text[i + 1] === '{') { depth++; i += 2; continue; }
          if (d === '}' && depth > 0) { depth--; i++; continue; }
          if (d === '"' && depth === 0) { closed = true; i++; break; }
          if (d === '\n' && depth === 0) break;
          i++;
        }
        if (!closed) { const p = at(start); out.push(mark(p.line, p.ch, 'HCL: string is not closed on this line (missing ")', 'error', text)); }
        continue;
      }
      if (pairs[c]) stack.push({ c, k: i });
      else if (c === '}' || c === ']' || c === ')') {
        const top = stack.pop();
        if (!top) { const p = at(i); out.push(mark(p.line, p.ch, 'HCL: "' + c + '" has no opening bracket', 'error', text)); }
        else if (pairs[top.c] !== c) {
          const p = at(i), q = at(top.k);
          out.push(mark(p.line, p.ch, 'HCL: "' + c + '" closes "' + top.c + '" from line ' + (q.line + 1) + ' (expected "' + pairs[top.c] + '")', 'error', text));
        }
      }
      i++;
    }
    stack.forEach((s) => { const p = at(s.k); out.push(mark(p.line, p.ch, 'HCL: "' + s.c + '" is never closed', 'error', text)); });
    const skipLines = new Set();
    skip.forEach(([a, b]) => { const pa = at(a).line, pb = at(b).line; for (let l = pa + 1; l <= pb; l++) skipLines.add(l); });
    text.split('\n').forEach((L, li) => {                // name =        (nothing after =)
      if (skipLines.has(li)) return;
      const m = L.match(/^(\s*)([A-Za-z_][\w-]*)\s*=\s*(#.*|\/\/.*)?$/);
      if (m) out.push({ from: CM.Pos(li, m[1].length), to: CM.Pos(li, L.length),
                        message: 'HCL: "' + m[2] + ' =" has no value', severity: 'error' });
    });
    return out;
  }

  // ------------------------------------------------------------------ Python (ruff on the server)
  async function lintPython(text, ed) {
    const files = (ed.opts.files && ed.opts.files()) || [{ name: 'main.py', content: text }];
    const cur = (ed.opts.fileName && ed.opts.fileName()) || 'main.py';
    if (!text.trim()) return [];
    try {
      const r = await fetch('/api/python-lint', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                                   body: JSON.stringify({ files: files.filter((f) => /\.py$/.test(f.name)) }) });
      if (!r.ok) return [];
      const d = await r.json();
      return (d.issues || []).filter((x) => (!x.file || x.file === cur) && !/^I\d/.test(x.code || '')).map((x) => {   // import order: not an error
        const sev = /^(F401|F841|E7\d\d|E4\d\d|W)/.test(x.code || '') ? 'warning' : 'error';
        return mark((x.line || 1) - 1, (x.col || 1) - 1, 'Python ' + (x.code ? x.code + ': ' : '') + x.message, sev, text);
      });
    } catch (e) { return []; }
  }

  // ------------------------------------------------------------------ language plumbing
  const MODES = {
    json: { name: 'javascript', json: true }, payload: { name: 'javascript', json: true },
    xml: 'xml', yaml: 'yaml', ansible: 'yaml', python: 'python', hcl: 'hcl', jinja: 'jinja2', text: null,
    'jinja-xml': 'xml', vars: 'yaml',
  };
  if (CM.defineSimpleMode && !CM.modes.hcl) {
    CM.defineSimpleMode('hcl', {
      start: [
        { regex: /(?:#|\/\/).*/, token: 'comment' },
        { regex: /\/\*/, token: 'comment', next: 'comment' },
        { regex: /"(?:[^\\"]|\\.)*?(?:"|$)/, token: 'string' },
        { regex: /<<-?\w+/, token: 'string-2' },
        { regex: /\b(?:resource|data|variable|output|locals|module|provider|terraform|dynamic|content|moved|import|check)\b/, token: 'keyword' },
        { regex: /\b(?:for_each|count|depends_on|lifecycle|source|version|for|in|if|each|self|var|local|null|true|false)\b/, token: 'variable-2' },
        { regex: /0x[a-f\d]+|[-+]?(?:\.\d+|\d+\.?\d*)(?:e[-+]?\d+)?/i, token: 'number' },
        { regex: /[A-Za-z_][\w-]*(?=\s*=)/, token: 'attribute' },
        { regex: /[A-Za-z_][\w-]*(?=\s*\()/, token: 'builtin' },
        { regex: /[{[(]/, indent: true }, { regex: /[}\])]/, dedent: true },
      ],
      comment: [{ regex: /.*?\*\//, token: 'comment', next: 'start' }, { regex: /.*/, token: 'comment' }],
      meta: { lineComment: '#', electricChars: '}]' },
    });
  }
  function langFor(name, yamlLang) {
    name = (name || '').toLowerCase();
    if (/\.(tf|tfvars|hcl)$/.test(name)) return 'hcl';
    if (/\.tfstate(\.backup)?$|\.lock\.hcl\.json$/.test(name)) return 'json';
    if (/\.(ya?ml)$/.test(name)) return yamlLang || 'ansible';
    if (/\.j2$|\.jinja2?$/.test(name)) return 'jinja';
    if (/\.json$/.test(name)) return 'json';
    if (/\.xml$/.test(name)) return 'xml';
    if (/\.py$/.test(name)) return 'python';
    if (/(^|\/)(hosts|inventory)[^/]*$/.test(name) && !/\./.test(name.split('/').pop())) return 'text';
    return 'text';
  }
  function effectiveLang(ed, text) {
    const t = text.trimStart();
    if (ed.lang === 'payload') return t[0] === '<' ? 'xml' : 'json';      // RESTCONF body: JSON or XML
    if (ed.lang === 'vars') return t[0] === '{' ? 'json' : 'yaml';        // variables: JSON or YAML
    return ed.lang;
  }
  async function annotations(text, options, cm) {
    const ed = cm._hied;
    if (!ed) return [];
    const lang = effectiveLang(ed, text);
    let res = [];
    try {
      if (lang === 'json') res = lintJSON(text);
      else if (lang === 'xml') res = lintXML(text);
      else if (lang === 'yaml') res = lintYAML(text, false);
      else if (lang === 'ansible') res = lintYAML(text, true).concat(/\{%/.test(text) ? lintJinja(text) : []);
      else if (lang === 'jinja') res = lintJinja(text);
      else if (lang === 'jinja-xml') { res = lintJinja(text); if (!res.length) res = lintXML(text.replace(/\{%[\s\S]*?%\}|\{#[\s\S]*?#\}/g, blank)); }
      else if (lang === 'hcl') res = lintHCL(text);
      else if (lang === 'python') res = await lintPython(text, ed);
    } catch (e) { res = []; }
    if (cm.getValue() !== text) return new Promise(() => {});   // text changed meanwhile: a newer check follows
    if (ed.external && ed.external.text === text) res = res.concat(ed.external.items);
    if (ed.status) {
      const errs = res.filter((x) => x.severity === 'error').length, warns = res.length - errs;
      ed.status.textContent = !text.trim() || lang === 'text' ? '' :
        (errs ? '✖ ' + errs + ' error' + (errs > 1 ? 's' : '') : '✔ no errors') + (warns ? ' · ' + warns + ' warning' + (warns > 1 ? 's' : '') : '');
      ed.status.style.color = errs ? '#dc2626' : '#16a34a';
      ed.status.title = res.slice(0, 15).map((x) => 'line ' + (x.from.line + 1) + ': ' + x.message).join('\n');
    }
    return res;
  }
  function applyLang(cm, lang) {
    const ed = cm._hied;
    ed.lang = lang;
    const text = cm.getValue();
    const mode = MODES[effectiveLang(ed, text)] || null;
    cm.setOption('mode', mode);
    cm.setOption('lint', lang === 'text' ? false : { getAnnotations: annotations, delay: lang === 'python' ? 900 : 350 });
    cm.setOption('gutters', lang === 'text' ? ['CodeMirror-linenumbers'] : ['CodeMirror-lint-markers', 'CodeMirror-linenumbers']);
    cm.setOption('indentUnit', lang === 'python' ? 4 : 2);
    if (lang === 'hcl') tfSchema();
    if (ed.fmtBtn) ed.fmtBtn.style.display = ['json', 'payload', 'vars', 'xml', 'yaml', 'ansible', 'python', 'hcl', 'jinja', 'jinja-xml'].includes(lang) && !ed.opts.noFormat ? '' : 'none';
  }

  // ------------------------------------------------------------------ Terraform: ACI 2.17.0 schema suggestions
  // static/terraform/aci-2.17.0.json (tools/trim_tf_schema.py): {r: resources, d: data sources, p: provider}
  let TFS = null, TFS_P = null;
  function tfSchema() {
    if (!TFS_P) TFS_P = fetch('/static/terraform/aci-2.17.0.json').then((r) => (r.ok ? r.json() : null))
      .then((j) => { TFS = j; return j; }).catch(() => null);
    return TFS;
  }
  // which schema node the cursor is in: walk the braces before it
  function hclNode(text) {
    if (!TFS) return null;
    const stack = [];                                     // {ch, node}
    const top = () => (stack.length ? stack[stack.length - 1].node : undefined);
    let seg = '', i = 0, q = false;
    while (i < text.length) {
      const c = text[i];
      if (q) { seg += c; if (c === '\\') { seg += text[i + 1] || ''; i++; } else if (c === '"') q = false; i++; continue; }
      if (c === '"') { q = true; seg += '"'; i++; continue; }
      if (c === '#' || (c === '/' && text[i + 1] === '/')) { while (i < text.length && text[i] !== '\n') i++; continue; }
      if (c === '/' && text[i + 1] === '*') { const e = text.indexOf('*/', i + 2); i = e < 0 ? text.length : e + 2; continue; }
      if (c === '{' || c === '[') {
        const h = seg.trim().split('\n').pop().trim(), cur = top();
        let node = null, m;
        if (c === '[') node = (m = h.match(/^([\w-]+)\s*=$/)) && cur && cur.a && cur.a[m[1]] ? { list: cur.a[m[1]][2] || null } : null;
        else if ((m = h.match(/^(resource|data)\s+"([\w-]+)"/))) node = (m[1] === 'resource' ? TFS.r : TFS.d)[m[2]] || null;
        else if (/^provider\s+"aci"/.test(h)) node = TFS.p;
        else if (!stack.length) node = null;
        else if ((m = h.match(/^dynamic\s+"([\w-]+)"$/))) node = cur && cur.b ? cur.b[m[1]] || null : null;
        else if (h === 'content') node = cur || null;
        else if ((m = h.match(/^([\w-]+)\s*=$/))) node = cur && cur.a && cur.a[m[1]] ? cur.a[m[1]][2] || null : null;
        else if ((m = h.match(/^([\w-]+)$/))) node = cur && cur.b ? cur.b[m[1]] || null : null;
        else if (h === '' && cur && cur.list !== undefined) node = cur.list;   // { } inside  attr = [ ... ]
        stack.push({ ch: c, node }); seg = ''; i++; continue;
      }
      if (c === '}' || c === ']') { stack.pop(); seg = ''; i++; continue; }
      if (c === '\n' || c === ',') { seg += c; i++; continue; }
      seg += c; i++;
    }
    return top() || null;
  }
  function hclHint(cm, cur, line) {
    if (!tfSchema()) return null;
    const before = line.slice(0, cur.ch);
    let m = before.match(/^\s*(resource|data)\s+"([\w-]*)$/);
    if (m) {
      const pool = m[1] === 'resource' ? TFS.r : TFS.d, w = m[2];
      const list = Object.keys(pool).filter((k) => k.startsWith(w)).sort().slice(0, 400)
        .map((k) => ({ text: k + '"', displayText: k + (pool[k].d ? '  — ' + pool[k].d : ''), className: 'hied-hint' }));
      return list.length ? { list, from: CM.Pos(cur.line, cur.ch - w.length), to: cur } : null;
    }
    m = before.match(/^(\s*)([\w-]*)$/);
    if (!m) return null;
    const node = hclNode(cm.getRange(CM.Pos(0, 0), CM.Pos(cur.line, 0)) + m[1]);
    if (!node || !node.a) return null;
    const w = m[2], list = [];
    const FIRST = ['parent_dn', 'tenant_dn', 'contract_dn', 'filter_dn', 'application_epg_dn', 'name', 'description'];
    const rank = (k) => (node.a[k][0] === 'r' ? 0 : FIRST.includes(k) ? 1 + FIRST.indexOf(k) / 10 : 2);
    Object.keys(node.a).sort((x, y) => rank(x) - rank(y) || x.localeCompare(y)).forEach((k) => {
      if (!k.startsWith(w)) return;
      const [f, d, sub] = node.a[k];
      list.push({ text: k + (sub ? ' = {\n' + m[1] + '  \n' + m[1] + '}' : ' = '), displayText: k + (f === 'r' ? ' *' : '') + (sub ? ' {…}' : '') + (d ? '  — ' + d : ''),
                  className: f === 'r' ? 'hied-hint hied-req' : 'hied-hint',
                  hint: sub ? (c, data, it) => { c.replaceRange(it.text, data.from, data.to); c.setCursor(CM.Pos(data.from.line + 1, m[1].length + 2)); } : undefined });
    });
    Object.keys(node.b || {}).sort().forEach((k) => {
      if (k.startsWith(w)) list.push({ text: k + ' {\n' + m[1] + '  \n' + m[1] + '}', displayText: k + ' { block }' + (node.b[k].d ? '  — ' + node.b[k].d : ''), className: 'hied-hint',
                                       hint: (c, data, it) => { c.replaceRange(it.text, data.from, data.to); c.setCursor(CM.Pos(data.from.line + 1, m[1].length + 2)); } });
    });
    return list.length ? { list, from: CM.Pos(cur.line, cur.ch - w.length), to: cur } : null;
  }

  // ------------------------------------------------------------------ suggestions
  const WORDS = {
    hcl: ['resource', 'data', 'variable', 'output', 'locals', 'module', 'provider', 'terraform', 'required_providers',
          'required_version', 'source', 'version', 'for_each', 'count', 'depends_on', 'lifecycle', 'dynamic', 'content',
          'each.key', 'each.value', 'var.', 'local.', 'toset', 'tomap', 'tolist', 'flatten', 'lookup', 'merge', 'keys',
          'values', 'length', 'concat', 'contains', 'jsonencode', 'jsondecode', 'format', 'join', 'split', 'sensitive',
          'description', 'type', 'default', 'string', 'number', 'bool', 'list(string)', 'map(string)', 'object({',
          'parent_dn', 'tenant_dn', 'name', 'annotation', 'relation_to_vrf', 'relation_to_bridge_domain', 'insecure',
          'username', 'password', 'url'],
    ansible: ['hosts', 'gather_facts', 'become', 'tasks', 'vars', 'vars_files', 'roles', 'handlers', 'name', 'when',
              'loop', 'with_items', 'register', 'tags', 'notify', 'delegate_to', 'connection', 'ansible_connection',
              'ansible_network_os', 'ansible_host', 'ansible_user', 'ansible_password', 'ansible.netcommon.network_cli',
              'ansible.netcommon.netconf', 'ansible.netcommon.httpapi', 'cisco.ios.ios_config', 'cisco.ios.ios_command',
              'cisco.ios.ios_facts', 'cisco.ios.ios_interfaces', 'cisco.ios.ios_l3_interfaces', 'cisco.ios.ios_static_routes',
              'cisco.nxos.nxos_config', 'cisco.nxos.nxos_command', 'cisco.nxos.nxos_static_routes', 'cisco.aci.aci_tenant',
              'cisco.aci.aci_vrf', 'cisco.aci.aci_bd', 'cisco.aci.aci_ap', 'cisco.aci.aci_epg', 'cisco.aci.aci_rest',
              'ansible.builtin.debug', 'ansible.builtin.template', 'ansible.builtin.uri', 'ansible.builtin.set_fact',
              'ansible.builtin.assert', 'ansible.builtin.include_tasks', 'ansible.builtin.import_tasks', 'state', 'config',
              'lines', 'parents', 'commands', 'msg', 'var', 'that', 'merged', 'replaced', 'overridden', 'deleted', 'gathered'],
    python: ['import', 'from', 'def', 'class', 'return', 'print', 'requests', 'json', 'yaml', 'netmiko', 'ConnectHandler',
             'ncclient', 'manager', 'xmltodict', 'response', 'status_code', 'raise_for_status', 'verify=False', 'headers',
             'auth', 'timeout', 'with', 'open', 'enumerate', 'isinstance', 'Exception', 'try', 'except', 'finally'],
  };
  function hint(cm) {
    const ed = cm._hied, cur = cm.getCursor(), line = cm.getLine(cur.line);
    let s = cur.ch; while (s > 0 && /[\w.\-:(]/.test(line[s - 1])) s--;
    const word = line.slice(s, cur.ch);
    const lang = ed ? effectiveLang(ed, cm.getValue()) : 'text';
    if (lang === 'hcl') { const h = hclHint(cm, cur, line); if (h) return h; if (word.length < 3) return null; }
    if (word.length < 1) return null;
    const pool = new Set(WORDS[lang === 'yaml' ? 'ansible' : lang] || []);
    const any = CM.hint.anyword ? CM.hint.anyword(cm, { word: /[\w.\-]+/ }) : null;
    (any ? any.list : []).forEach((w) => pool.add(w));
    const lw = word.toLowerCase();
    const list = [...pool].filter((w) => w !== word && w.toLowerCase().startsWith(lw)).sort().slice(0, 60);
    return list.length ? { list, from: CM.Pos(cur.line, s), to: cur } : null;
  }

  // ------------------------------------------------------------------ ✨ Format (auto-correction)
  function formatJSON(text) {
    // placeholders: inside a string -> n ; as a value -> "n"
    const toks = [];
    let out = '', inStr = false;
    for (let i = 0; i < text.length;) {
      const m = (text[i] === '{' && /^\{[{%#]/.test(text.slice(i, i + 2))) ? text.slice(i).match(/^\{\{[\s\S]*?\}\}|^\{%[\s\S]*?%\}|^\{#[\s\S]*?#\}/) : null;
      if (m) { toks.push(m[0]); out += inStr ? '' + (toks.length - 1) + '' : '"' + (toks.length - 1) + '"'; i += m[0].length; continue; }
      const c = text[i];
      if (c === '\\' && inStr) { out += c + (text[i + 1] || ''); i += 2; continue; }
      if (c === '"') inStr = !inStr;
      out += c; i++;
    }
    const pretty = JSON.stringify(JSON.parse(out), null, 2);
    return pretty.replace(/"(\d+)"/g, (_, n) => toks[+n]).replace(/(\d+)/g, (_, n) => toks[+n]);
  }
  function formatXML(text) {
    if (/\{\{|\{%/.test(text)) throw new Error('contains {{ }} / {% %} — not reformatted');
    const decl = (text.match(/^\s*(<\?xml[^>]*\?>)/) || [])[1];
    const doc = new DOMParser().parseFromString('<r>' + text.replace(/^\s*<\?xml[^>]*\?>/, '') + '</r>', 'application/xml');
    if (doc.getElementsByTagName('parsererror')[0]) throw new Error('fix the XML errors first');
    const ser = new XMLSerializer(), lines = [];
    const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const hasText = (el) => [...el.childNodes].some((k) => (k.nodeType === 3 || k.nodeType === 4) && k.nodeValue.trim());
    function walk(node, depth) {
      const pad = '  '.repeat(depth);
      node.childNodes.forEach((ch) => {
        if (ch.nodeType === 3) { if (ch.nodeValue.trim()) lines.push(pad + esc(ch.nodeValue)); return; }
        if (ch.nodeType === 8) { lines.push(pad + '<!--' + ch.nodeValue + '-->'); return; }
        if (ch.nodeType === 4) { lines.push(pad + '<![CDATA[' + ch.nodeValue + ']]>'); return; }
        if (ch.nodeType === 7) { lines.push(pad + '<?' + ch.target + (ch.data ? ' ' + ch.data : '') + '?>'); return; }
        if (ch.nodeType !== 1) return;
        if (hasText(ch) && [...ch.childNodes].some((k) => k.nodeType !== 3)) { lines.push(pad + ser.serializeToString(ch)); return; }  // mixed content: as is
        let attrs = '';
        for (const a of ch.attributes) attrs += ' ' + a.name + '="' + a.value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;') + '"';
        const kids = [...ch.childNodes].filter((k) => !(k.nodeType === 3 && !k.nodeValue.trim()));
        if (!kids.length) lines.push(pad + '<' + ch.tagName + attrs + '/>');
        else if (kids.length === 1 && kids[0].nodeType === 3) lines.push(pad + '<' + ch.tagName + attrs + '>' + esc(kids[0].nodeValue) + '</' + ch.tagName + '>');
        else { lines.push(pad + '<' + ch.tagName + attrs + '>'); walk(ch, depth + 1); lines.push(pad + '</' + ch.tagName + '>'); }
      });
    }
    walk(doc.documentElement, 0);
    return (decl ? decl + '\n' : '') + lines.join('\n') + '\n';
  }
  function fixWhitespace(text) {
    return text.split('\n').map((L) => L.replace(/^\t+/, (t) => '  '.repeat(t.length)).replace(/[ \t]+$/, '')).join('\n');
  }
  async function format(target) {
    const cm = target && target._hied ? target : target && target._hiedCm;
    if (!cm) return { ok: false, msg: 'no editor' };
    const ed = cm._hied, text = cm.getValue(), lang = effectiveLang(ed, text);
    if (!text.trim()) return { ok: false, msg: 'nothing to format' };
    try {
      let out = text;
      if (lang === 'json') out = formatJSON(text);
      else if (lang === 'xml') out = formatXML(text);
      else if (lang === 'yaml' || lang === 'ansible' || lang === 'jinja' || lang === 'jinja-xml') out = fixWhitespace(text);
      else if (lang === 'python') {
        const r = await fetch('/api/python-format', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                                       body: JSON.stringify({ content: text }) });
        const d = await r.json();
        if (!d.ok) return { ok: false, msg: d.error || 'could not format' };
        out = d.content;
      } else if (lang === 'hcl') {
        if (ed.opts.onFormat) return ed.opts.onFormat();
        out = fixWhitespace(text);
      } else return { ok: false, msg: 'no formatter for this file' };
      if (out !== text) {
        const cur = cm.getCursor(), top = cm.getScrollInfo().top;
        cm.operation(() => { cm.setValue(out); cm.setCursor(cur); cm.scrollTo(null, top); });
        cm._hiedFire && cm._hiedFire();
      }
      return { ok: true, msg: out === text ? 'already tidy' : '✔ formatted' };
    } catch (e) { return { ok: false, msg: String(e.message || e) }; }
  }

  // ------------------------------------------------------------------ attach to a textarea
  const NATIVE_VALUE = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
  const NATIVE_DISABLED = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'disabled') ||
                          Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'disabled');
  function toolbar(cm, ed) {
    const bar = document.createElement('div');
    bar.className = 'hied-bar';
    bar.innerHTML = '<span class="hied-status"></span><span style="flex:1"></span>' +
      '<button type="button" class="hied-fmt" title="Fix layout: JSON / XML pretty-print, Python ruff format, Terraform fmt, YAML tabs + trailing spaces">✨ Format</button>' +
      '<span class="hied-msg"></span>';
    ed.status = bar.querySelector('.hied-status');
    ed.fmtBtn = bar.querySelector('.hied-fmt');
    const msg = bar.querySelector('.hied-msg');
    ed.fmtBtn.onclick = async () => {
      const r = await format(cm);
      msg.textContent = r.msg; msg.style.color = r.ok ? '#16a34a' : '#dc2626';
      setTimeout(() => { msg.textContent = ''; }, 2500);
    };
    return bar;
  }
  function baseOptions(lang) {
    return {
      lineNumbers: true, matchBrackets: true, autoCloseBrackets: true, showTrailingSpace: true,
      styleActiveLine: true, indentWithTabs: false, tabSize: 2, viewportMargin: 30, lineWrapping: false,
      extraKeys: {
        Tab: (c) => c.somethingSelected() ? c.indentSelection('add') : c.replaceSelection(' '.repeat(c.getOption('indentUnit')), 'end'),
        'Shift-Tab': (c) => c.indentSelection('subtract'),
        'Ctrl-Space': (c) => c.showHint({ hint, completeSingle: false }),
      },
    };
  }
  function wireCommon(cm, ed) {
    cm.on('inputRead', (c, ch) => {
      if (c.state.completionActive || ch.origin !== '+input') return;
      const t = ch.text.join('');
      if (/^[\w.]$/.test(t)) {
        const cur = c.getCursor(), L = c.getLine(cur.line).slice(0, cur.ch);
        if (/[\w.]{3,}$/.test(L) || (c._hied && c._hied.lang === 'hcl' && /^\s*[\w-]{1,}$|^\s*(resource|data)\s+"[\w-]*$/.test(L)))
          c.showHint({ hint, completeSingle: false });
      }
    });
    // show it again when it becomes visible (tabs, collapsed panes)
    const el = cm.getWrapperElement();
    if (window.IntersectionObserver) new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && cm.refresh())).observe(el);
    if (window.ResizeObserver) new ResizeObserver(() => cm.refresh()).observe(el);
    void ed;
  }
  function attach(ta, opts) {
    if (!ta || ta._hiedCm) return ta && ta._hiedCm;
    opts = opts || {};
    const initial = NATIVE_VALUE.get.call(ta);
    const h = opts.height || (ta.style.height) || ((parseInt(ta.getAttribute('rows'), 10) || 8) * 18 + 12) + 'px';
    const cm = CM(function (el) { ta.parentNode.insertBefore(el, ta.nextSibling); },
                  Object.assign(baseOptions(opts.lang), { value: initial, placeholder: ta.getAttribute('placeholder') || '' }));
    const ed = { lang: opts.lang || 'text', opts, external: null };
    cm._hied = ed; ta._hiedCm = cm;
    cm.setSize('100%', h);
    ta.style.display = 'none';
    const wrap = cm.getWrapperElement();
    wrap.classList.add('hied');
    wrap.style.resize = 'vertical';
    if (!opts.noBar) wrap.parentNode.insertBefore(toolbar(cm, ed), wrap.nextSibling);
    applyLang(cm, ed.lang);
    wireCommon(cm, ed);

    let silent = false;
    Object.defineProperty(ta, 'value', {
      configurable: true,
      get() { return cm.getValue(); },
      set(v) { silent = true; cm.setValue(v == null ? '' : String(v)); cm.clearHistory(); silent = false;
               if (ed.lang === 'payload' || ed.lang === 'vars') applyLang(cm, ed.lang); },
    });
    if (NATIVE_DISABLED) Object.defineProperty(ta, 'disabled', {
      configurable: true,
      get() { return NATIVE_DISABLED.get.call(ta); },
      set(v) { NATIVE_DISABLED.set.call(ta, v); cm.setOption('readOnly', v ? 'nocursor' : false); wrap.classList.toggle('hied-disabled', !!v); },
    });
    if (ta.disabled) { cm.setOption('readOnly', 'nocursor'); wrap.classList.add('hied-disabled'); }
    ta.focus = () => cm.focus();
    ta.scrollIntoView = (o) => wrap.scrollIntoView(o);
    const fire = () => ta.dispatchEvent(new Event('input', { bubbles: true }));
    cm._hiedFire = fire;
    cm.on('change', () => {
      if (ed.external && ed.external.text !== cm.getValue()) ed.external = null;
      if (ed.lang === 'payload' || ed.lang === 'vars') { const m = MODES[effectiveLang(ed, cm.getValue())]; if (JSON.stringify(m) !== JSON.stringify(cm.getOption('mode'))) cm.setOption('mode', m); }
      if (!silent) fire();
    });
    cm.on('blur', () => ta.dispatchEvent(new Event('change', { bubbles: true })));
    cm.on('keydown', (c, e) => {                        // Ctrl+S, Enter… handlers on the textarea
      if (e.key === 'Tab') return;
      const ev = new KeyboardEvent('keydown', { key: e.key, code: e.code, ctrlKey: e.ctrlKey, metaKey: e.metaKey,
                                                 shiftKey: e.shiftKey, altKey: e.altKey, bubbles: true, cancelable: true });
      ta.dispatchEvent(ev);
      if (ev.defaultPrevented) e.preventDefault();
    });
    return cm;
  }
  function enhance(cm, opts) {
    if (cm._hied) return cm;
    opts = opts || {};
    const ed = { lang: opts.lang || 'text', opts, external: null };
    cm._hied = ed;
    const base = baseOptions(ed.lang);
    ['matchBrackets', 'autoCloseBrackets', 'showTrailingSpace', 'styleActiveLine'].forEach((k) => cm.setOption(k, base[k]));
    cm.setOption('extraKeys', Object.assign({}, cm.getOption('extraKeys') || {}, { 'Ctrl-Space': base.extraKeys['Ctrl-Space'] }));
    const wrap = cm.getWrapperElement();
    wrap.classList.add('hied');
    if (!opts.noBar) wrap.parentNode.insertBefore(toolbar(cm, ed), wrap.nextSibling);
    applyLang(cm, ed.lang);
    wireCommon(cm, ed);
    cm.on('change', () => { if (ed.external && ed.external.text !== cm.getValue()) ed.external = null; });
    return cm;
  }
  function cmOf(t) { return t && (t._hied ? t : t._hiedCm); }
  function setLang(t, lang) { const cm = cmOf(t); if (cm) applyLang(cm, lang); }
  // results from the server (terraform validate) shown until the text changes
  function setExternal(t, items) {
    const cm = cmOf(t); if (!cm) return;
    const text = cm.getValue();
    cm._hied.external = { text, items: (items || []).map((x) => x.from ? x : mark(x.line, x.ch || 0, x.message, x.severity, text)) };
    cm.performLint && cm.performLint();
  }

  window.HiEd = { attach, enhance, setLang, langFor, format, setExternal, cmOf,
                  _lint: { json: lintJSON, xml: lintXML, yaml: lintYAML, jinja: lintJinja, hcl: lintHCL },
                  _fmt: { json: formatJSON, xml: formatXML, ws: fixWhitespace } };
})();
