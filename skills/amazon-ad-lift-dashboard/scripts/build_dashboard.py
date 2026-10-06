#!/usr/bin/env python3
"""从领星「ASIN 表现」导出生成「排名 × 广告费 × 方案偏差」单文件 HTML 看板。

python build_dashboard.py --data export.xlsx --match 款名=三头 --out dashboard.html
    [--countries 美国,加拿大] [--phases phases.json] [--plan plan.json --pre A:B --post C:D]
    [--notes notes.json] [--title 标题] [--dump-json data.json]

先不带 --notes 跑一遍拿到 data.json（含自动分段与各阶段统计），读数后写 notes.json 再跑一遍。
"""
import argparse, json, os, sys, warnings
import pandas as pd
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ad_increment as AI

TYPES = ['SP', 'SB', 'SBV', 'SD']
NUM = {'spend': '广告花费', 'clicks': '点击', 'impr': '展示', 'adsales': '广告销售额', 'sales': '销售额', 'units': '销量',
       'orders': '订单量', 'adorders': '广告订单量', 'sess': 'Sessions-Total', 'gp': '订单毛利润'}

def parse_rank(s):
    s = s.astype(str)
    return s.str.split('：').str[0], pd.to_numeric(s.str.split('：').str[-1], errors='coerce')

def daily(df):
    df = df.copy()
    df['cat'], df['r'] = parse_rank(df['小类排名'])
    _, df['b'] = parse_rank(df['大类排名'])
    agg = {k: (v, 'sum') for k, v in NUM.items() if v in df}
    for t in TYPES:
        for k, c in (('spend', '广告费'), ('sales', '广告销售额'), ('orders', '广告订单量')):
            if t + c in df: agg[f'{t}_{k}'] = (t + c, 'sum')
    g = df.groupby('日期').agg(rank=('r', 'min'), big=('b', 'min'), **agg).reset_index()
    best = df.loc[df['r'].notna()]
    cat = best.loc[best.groupby('日期')['r'].idxmin(), 'cat'].mode()
    return g, (cat.iloc[0] if len(cat) else '')

def auto_phases(ranks, min_len=3, max_n=6):
    """按最好排名的连续区间切段，短段并入排名更接近的邻段，最多 max_n 段。"""
    segs = []
    for i, r in enumerate(ranks):
        if segs and segs[-1]['r'] == r: segs[-1]['e'] = i
        else: segs.append({'s': i, 'e': i, 'r': r})
    def merge(k):
        a = segs[k]
        nb = [j for j in (k - 1, k + 1) if 0 <= j < len(segs)]
        j = min(nb, key=lambda j: (abs(segs[j]['r'] - a['r']), -(segs[j]['e'] - segs[j]['s'])))
        lo, hi = sorted((j, k))
        segs[lo] = {'s': segs[lo]['s'], 'e': segs[hi]['e'], 'r': segs[j]['r'], 'rs': segs[lo].get('rs', {segs[lo]['r']}) | segs[hi].get('rs', {segs[hi]['r']})}
        del segs[hi]
    while len(segs) > 1:
        lens = [s['e'] - s['s'] + 1 for s in segs]
        k = min(range(len(segs)), key=lambda i: lens[i])
        if lens[k] >= min_len and len(segs) <= max_n: break
        merge(k)
    return [(s['s'], s['e']) for s in segs]

def build_market(df, country, phases_cfg):
    g, cat = daily(df[df['国家'] == country])
    g = g[g['rank'].notna()].reset_index(drop=True)
    if g.empty: return None
    if phases_cfg:
        idx = {d.strftime('%Y-%m-%d'): i for i, d in enumerate(g['日期'])}
        cuts = [(idx[p['start']], idx[p['end']], p.get('name'), p.get('focus')) for p in phases_cfg]
    else:
        cuts = [(s, e, None, None) for s, e in auto_phases(g['rank'].astype(int).tolist())]
    best = int(g['rank'].min())
    phases = []
    for i, (s, e, name, focus) in enumerate(cuts):
        rr = g['rank'].iloc[s:e + 1]
        lo, hi = int(rr.min()), int(rr.max())
        phases.append({'label': chr(65 + i), 'si': s, 'ei': e,
                       'name': name or (f'排名 #{lo}' if lo == hi else f'排名 #{lo}-#{hi}'),
                       'focus': bool(focus) if focus is not None else (lo == best or (i == len(cuts) - 1 and lo <= best + 1))})
    tot = g['spend'].sum() or 1
    types = [t for t in TYPES if f'{t}_spend' in g and g[f'{t}_spend'].sum() >= 0.01 * tot]
    rows = []
    for _, r in g.iterrows():
        o = {'d': r['日期'].strftime('%m/%d'), 'rank': int(r['rank']), 'big': None if pd.isna(r['big']) else int(r['big'])}
        for k in NUM:
            if k in g: o[k] = round(float(r[k]), 2)
        for t in TYPES:
            for k in ('spend', 'sales', 'orders'):
                o[f'{t}_{k}'] = round(float(r.get(f'{t}_{k}', 0) or 0), 2)
        rows.append(o)
    return {'country': country, 'title': f'{country} · 最好排名 #{best}', 'cat': cat, 'best': best, 'types': types,
            'phases': phases, 'rows': rows, 'desc': '', 'notes': []}

def phase_summary(m):
    out = []
    for p in m['phases']:
        r = m['rows'][p['si']:p['ei'] + 1]; n = len(r); s = lambda k: sum(x.get(k, 0) or 0 for x in r)
        o = {'phase': p['label'] + ' ' + p['name'], 'range': r[0]['d'] + '~' + r[-1]['d'], 'days': n, 'focus': p['focus'],
             'spend_per_day': s('spend') / n, 'units_per_day': s('units') / n, 'sales_per_day': s('sales') / n,
             'acos': s('spend') / s('adsales') if s('adsales') else None, 'tacos': s('spend') / s('sales') if s('sales') else None,
             'cpc': s('spend') / s('clicks') if s('clicks') else None, 'gp_per_day': s('gp') / n,
             'ad_order_share': s('adorders') / s('orders') if s('orders') else None}
        for t in m['types']:
            sp, sa, od = s(f'{t}_spend'), s(f'{t}_sales'), s(f'{t}_orders')
            o[t] = {'spend_per_day': sp / n, 'acos': sp / sa if sa else None, 'roas': sa / sp if sp else None, 'cpo': sp / od if od else None}
        out.append(o)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True); ap.add_argument('--match', action='append'); ap.add_argument('--countries')
    ap.add_argument('--phases'); ap.add_argument('--plan'); ap.add_argument('--pre'); ap.add_argument('--post')
    ap.add_argument('--notes'); ap.add_argument('--title'); ap.add_argument('--end', help='只保留该日期之前（不含）的数据')
    ap.add_argument('--out', required=True); ap.add_argument('--dump-json')
    a = ap.parse_args()
    df = AI.load(a.data, None, a.match)
    # 去掉不完整的最后一天：当天销售额 < 前 7 天中位数的 20%
    if a.end: df = df[df['日期'] < a.end]
    else:
        ds = df.groupby('日期')['销售额'].sum()
        if len(ds) > 7 and ds.iloc[-1] < 0.2 * ds.iloc[-8:-1].median():
            print('剔除不完整的最后一天', ds.index[-1].date(), file=sys.stderr); df = df[df['日期'] < ds.index[-1]]
    cs = a.countries.split(',') if a.countries else df.groupby('国家')['销售额'].sum().sort_values(ascending=False).index[:2].tolist()
    pcfg = json.load(open(a.phases, encoding='utf-8')) if a.phases else {}
    notes = json.load(open(a.notes, encoding='utf-8')) if a.notes else {}
    markets = [m for m in (build_market(df, c, pcfg.get(c)) for c in cs) if m]
    for m in markets:
        mn = notes.get('markets', {}).get(m['country'], {})
        m['title'] = mn.get('title', m['title']); m['desc'] = mn.get('desc', ''); m['notes'] = mn.get('notes', [])
    d0, d1 = df['日期'].min().strftime('%Y-%m-%d'), df['日期'].max().strftime('%Y-%m-%d')
    data = {'title': notes.get('title', a.title or '排名与广告费看板'),
            'subtitle': notes.get('subtitle', f'{d0} ~ {d1} 日数据。排名取同站点所有 ASIN 当日最好的小类排名；金额单位同导出（通常 USD）。'),
            'kpis': notes.get('kpis', []), 'markets': markets, 'plan': None,
            'notes': {'types': notes.get('types', []), 'plan': notes.get('plan', []), 'summary': notes.get('summary', [])},
            'foot': notes.get('foot', '数据来源：领星 ASIN 表现报表导出。')}
    if a.plan:
        if not (a.pre and a.post): sys.exit('--plan 需要同时给 --pre 和 --post')
        cfg = json.load(open(a.plan, encoding='utf-8')); pres = AI.plan(cfg)
        act = AI.actual(df, a.pre, a.post, pres['contribution_margin'], pres, cfg.get('actual_type_map'))
        dd = df.groupby('日期')[[t + '广告费' for t in TYPES]].sum().reset_index()
        data['plan'] = AI.clean({'plan': pres, 'actual': act, 'post_start': pd.Timestamp(a.post.split(':')[0]).strftime('%m/%d'),
            'daily': [{'d': r['日期'].strftime('%m/%d'), **{t: round(float(r[t + '广告费']), 2) for t in TYPES}} for _, r in dd.iterrows()],
            'desc': notes.get('plan_desc', f'执行前 = {a.pre.replace(":", " ~ ")}，执行后 = {a.post.replace(":", " ~ ")}，均按天数换算为 30 天月度值；全站点口径（受 --match/--countries 以外的筛选影响）。')})
    html = open(os.path.join(HERE, '..', 'assets', 'template.html'), encoding='utf-8').read()
    html = html.replace('__TITLE__', data['title']).replace('/*__DATA__*/null', json.dumps(AI.clean(data), ensure_ascii=False))
    open(a.out, 'w', encoding='utf-8').write(html)
    summ = {'markets': {m['country']: {'category': m['cat'], 'best_rank': m['best'], 'types': m['types'], 'phases': phase_summary(m)} for m in markets}}
    if data['plan']: summ['plan_vs_actual'] = data['plan']['actual']['vs_plan']
    s = json.dumps(AI.clean(summ), ensure_ascii=False, indent=1)
    if a.dump_json: open(a.dump_json, 'w', encoding='utf-8').write(s)
    print(s[:6000])

if __name__ == '__main__':
    main()
