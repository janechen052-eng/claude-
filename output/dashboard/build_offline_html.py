import json,re,os,sys
D='/tmp/claude-0/-home-user-claude-/48dd8f3e-d693-547b-985e-be7645ed24ff/scratchpad/dash/'
E='/tmp/claude-0/-home-user-claude-/48dd8f3e-d693-547b-985e-be7645ed24ff/scratchpad/export/'
page=open(D+'index.html',encoding='utf-8').read()
page=page.replace('<meta name="dash-one-writer">\n','')
imgs=open(D+'images.js',encoding='utf-8').read()
page=page.replace('<script src="images.js"></script>','<script>\n'+imgs+'</script>')
ds=['core_inventory','clearance_scenarios','channel_prices','cost_inputs','ops_plan','amazon_monthly','tiktok_temu_monthly','unit_economics','inventory_age','consumption_plan']
data={k:open(D+k+'.csv',encoding='utf-8').read() for k in ds}
d3js=open(E+'package/dist/d3.min.js',encoding='utf-8').read()
shim=r"""
(function(){
  const RAW = %s;
  const store = {}; const calcs = {}; const order = []; const draws = {}; const onDataFns = [];
  for (const k in RAW) { const rows = d3.csvParse(RAW[k].trim()); store[k] = { status: 'ok', data: rows.slice(), columns: rows.columns, meta: [], refreshing: false }; }
  function getCalc(id) {
    const c = calcs[id];
    if (!c.done) { c.value = c.fn(...c.inputs.map((i) => dash.data(i).data)); c.done = true; }
    return { status: 'ok', data: c.value, columns: c.value && c.value[0] ? Object.keys(c.value[0]) : [], meta: [], refreshing: false };
  }
  const dash = {
    colors: ['#2f6fdb', '#e0802b', '#2a9d8f', '#8e5cc4', '#d14b6a', '#7a8b2e', '#5b6b7f', '#c49a1f'],
    data(id) { if (store[id]) return store[id]; if (calcs[id]) return getCalc(id); return { status: 'missing', data: [], columns: [], meta: [] }; },
    calc(id, spec) { calcs[id] = { fn: spec.fn, inputs: spec.inputs || [], done: false }; order.push(id); },
    loader() {}, onData(fn) { onDataFns.push(fn); },
    draw(name, fn) {
      if (fn) { draws[name] = fn; return; }
      runDraw(name);
    },
    params() { return {}; }, setParams() {}, resetParams() {}, setLink() {}, refresh() {}
  };
  function runDraw(name) {
    const fn = draws[name]; if (!fn) return;
    document.querySelectorAll('[data-draw="' + name + '"]').forEach((el) => {
      try { if (typeof fn === 'function') fn(el); } catch (e) { console.error('draw ' + name, e); }
    });
  }
  function renderAll() {
    onDataFns.forEach((f) => { try { f(); } catch (e) { console.error(e); } });
    Object.keys(draws).forEach(runDraw);
  }
  window.dash = dash;
  window.__dashRender = renderAll;
  let w = window.innerWidth, t;
  window.addEventListener('resize', () => { if (window.innerWidth === w) return; w = window.innerWidth; clearTimeout(t); t = setTimeout(renderAll, 150); });
  // 切换页签后重画该页签
  document.addEventListener('click', (ev) => { if (ev.target.closest && ev.target.closest('.op-tab')) setTimeout(() => runDraw('cons'), 0); });
})();
""" % json.dumps(data, ensure_ascii=False)
css=r"""
:root {
  --font-anthropic-sans: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-anthropic-serif: Georgia, "Songti SC", "Noto Serif SC", "Times New Roman", serif;
  --color-bg: #f6f7f9; --color-panel: #ffffff; --color-fg: #1d2330; --color-fg-muted: #5f6878; --color-border-line: #e2e5ea;
  --color-ok: #1f8a4c; --color-warn: #b8680a; --color-bad: #c8364a;
  --cds-text-secondary: #5f6878; --cds-border: #cfd4dc; --cds-surface-popover: #ffffff; --cds-shadow-popover: 0 4px 16px rgba(20,30,50,.12);
  --cds-chart-grid: #eceef2; --cds-chart-axis: #b9bfc9; --cds-chart-reference: #7d8594; --cds-chart-muted: #b4bac4; --cds-chart-status-critical: #c8364a;
  --cds-font-size-caption: 12px; --cds-font-size-body: 14px; --cds-font-size-heading: 16px; --cds-font-size-title: 28px; --cds-font-weight-medium: 600;
  --cds-gap-xs: 4px; --cds-gap-sm: 8px; --cds-gap-md: 12px; --cds-gap-lg: 20px; --cds-gap-xl: 32px;
  --cds-pad-xs: 4px; --cds-pad-sm: 8px; --cds-pad-md: 12px; --cds-pad-lg: 16px; --cds-radius: 8px;
  --cds-dur-slow: .3s; --cds-ease-out: cubic-bezier(.2,.7,.2,1);
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --color-bg: #12151b; --color-panel: #1a1e26; --color-fg: #e7e9ee; --color-fg-muted: #9aa3b2; --color-border-line: #2b313c;
    --color-ok: #4cc27f; --color-warn: #e6a04a; --color-bad: #ef6b7d;
    --cds-text-secondary: #9aa3b2; --cds-border: #3a414d; --cds-surface-popover: #222733; --cds-shadow-popover: 0 4px 16px rgba(0,0,0,.4);
    --cds-chart-grid: #262b35; --cds-chart-axis: #4a5260; --cds-chart-reference: #8f98a8; --cds-chart-muted: #5b6372; --cds-chart-status-critical: #ef6b7d;
    color-scheme: dark;
  }
}
html, body { margin: 0; background: var(--color-bg); color: var(--color-fg); font-family: var(--font-anthropic-sans); font-size: 14px; }
#dash-root { max-width: 1280px; margin-inline: auto; padding: 24px max(16px, env(safe-area-inset-right, 0px)) 48px max(16px, env(safe-area-inset-left, 0px)); box-sizing: border-box; }
#dash-root *, #dash-root *::before, #dash-root *::after { box-sizing: border-box; }
.dash-skeleton:empty { min-height: 1em; }
.op-export-note { font-size: 12px; color: var(--color-fg-muted); margin: 0 0 16px; }
"""
html=f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>油泵清货看板</title>
<style>{css}</style>
<script>{d3js}</script>
<script>{shim}</script>
</head>
<body>
<div id="dash-root">
<p class="op-export-note">离线版 · 导出于 2026-11-03 · 数据：领星亚马逊/TikTok/TEMU 导出、油泵品线看板、运营方案；渠道计划与费率为测算假设。蓝框数字可改，修改不保存，刷新即恢复。</p>
{page}
</div>
<script>window.__dashRender();</script>
</body>
</html>
"""
out='/home/user/claude-/output/油泵清货看板_离线版.html'
open(out,'w',encoding='utf-8').write(html)
print(out, len(html))
