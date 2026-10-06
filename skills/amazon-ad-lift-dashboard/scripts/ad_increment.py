#!/usr/bin/env python3
"""站内广告优化：增量订单测算 + 边际利润 + 方案 vs 实际偏差。

用法:
  python ad_increment.py plan   --config plan.json [--out result.json]
  python ad_increment.py actual --data export.xlsx --pre 2026-09-01:2026-09-21 --post 2026-09-22:2026-10-05
                                [--country 美国] [--match 款名=三头] [--plan plan.json] [--cm 0.3022] [--out result.json]

plan.json 结构见 assets/plan_example.json。所有金额按同一币种（通常 USD）。
"""
import argparse, json, sys, math

# ---------------------------------------------------------------- plan
def lever_calc(lv, base):
    """单个投放动作的增量测算。返回 clicks / orders / spend / sales。"""
    cvr = lv.get('cvr', base['cvr'])
    cpc = lv.get('cpc', base['cpc'])
    aov = base['aov']
    t = lv['type']
    if t == 'ctr':
        # 展示量不变，CTR 从 from 提升到 to：增量点击 = 展示 × ΔCTR，花费按当前 CPC
        impr = lv.get('impressions', base['impressions'])
        ctr_from = lv.get('ctr_from', base['clicks'] / base['impressions'])
        d_clicks = impr * (lv['ctr_to'] - ctr_from)
        d_spend = d_clicks * cpc
    elif t == 'budget':
        # 加预算：预算全部花完，增量点击 = 预算 ÷ CPC
        d_spend = lv['budget']
        d_clicks = d_spend / cpc
    elif t == 'cpc':
        # 降价/提价：同预算下点击变化 = 预算/新CPC − 预算/旧CPC
        spend = lv.get('spend', base['clicks'] * base['cpc'])
        d_clicks = spend / lv['cpc_to'] - spend / cpc
        d_spend = 0.0
    else:
        raise ValueError('未知 lever type: %s' % t)
    d_orders = d_clicks * cvr
    return {'name': lv.get('name', t), 'type': t, 'clicks': d_clicks, 'orders': d_orders,
            'spend': d_spend, 'sales': d_orders * aov, 'cpc': cpc, 'cvr': cvr,
            'cpo': d_spend / d_orders if d_orders else None,
            'roas': d_orders * aov / d_spend if d_spend else None}

def contribution_margin(b):
    """加广告前贡献利润率：优先用给定值，否则 1 − 其他成本占比 − 退款率。"""
    if 'contribution_margin' in b:
        return b['contribution_margin']
    return 1 - b['other_cost_ratio'] - b.get('refund_rate', 0)

def plan(cfg):
    b = cfg['baseline']
    if 'cpc' not in b: b['cpc'] = b['ad_spend_sp'] / b['clicks'] if 'ad_spend_sp' in b else None
    if 'aov' not in b: b['aov'] = b['sales'] / b['orders']
    cm = contribution_margin(b)
    levers = [lever_calc(lv, b) for lv in cfg['levers']]
    tot = {k: sum(l[k] for l in levers) for k in ('clicks', 'orders', 'spend', 'sales')}
    d_profit = tot['sales'] * cm - tot['spend']
    before = {'sales': b['sales'], 'ad_spend': b['ad_spend'], 'gp': b['gp'], 'orders': b['orders']}
    after = {'sales': b['sales'] + tot['sales'], 'ad_spend': b['ad_spend'] + tot['spend'],
             'gp': b['gp'] + d_profit, 'orders': b['orders'] + tot['orders']}
    for x in (before, after):
        x['gp_rate'] = x['gp'] / x['sales']; x['tacos'] = x['ad_spend'] / x['sales']; x['roas_total'] = x['sales'] / x['ad_spend']
    return {
        'contribution_margin': cm, 'aov': b['aov'],
        'breakeven_roas': 1 / cm, 'breakeven_cpo': b['aov'] * cm,
        'levers': levers, 'total': tot,
        'incremental': {'profit': d_profit, 'profit_per_order': d_profit / tot['orders'] if tot['orders'] else None,
                        'marginal_margin': d_profit / tot['sales'] if tot['sales'] else None,
                        'roas': tot['sales'] / tot['spend'] if tot['spend'] else None,
                        'cpo': tot['spend'] / tot['orders'] if tot['orders'] else None,
                        'avg_profit_per_order_before': b['gp'] / b['orders']},
        'before': before, 'after': after,
        'delta': {'gp_rate_pt': (after['gp_rate'] - before['gp_rate']) * 100,
                  'tacos_pt': (after['tacos'] - before['tacos']) * 100,
                  'sales_pct': tot['sales'] / b['sales'] * 100,
                  'gp_pct': d_profit / b['gp'] * 100},
    }

# ---------------------------------------------------------------- actual
TYPES = ['SP', 'SB', 'SBV', 'SD']
COLS = ['销售额', '订单量', '销量', '广告花费', '广告销售额', '广告订单量', '展示', '点击', '订单毛利润', '结算毛利润',
        'Sessions-Total'] + [t + s for t in TYPES for s in ('广告费', '广告销售额', '广告订单量')]

def load(path, country=None, match=None):
    import pandas as pd, warnings
    warnings.filterwarnings('ignore')
    df = pd.read_excel(path) if path.endswith(('xlsx', 'xls')) else pd.read_csv(path)
    df['日期'] = pd.to_datetime(df['日期'])
    if country: df = df[df['国家'] == country]
    for m in match or []:
        col, val = m.split('=', 1)
        df = df[df[col].astype(str).str.contains(val, regex=False)]
    for c in COLS:
        if c not in df.columns: df[c] = 0
    return df

def window(df, rng, days=30):
    a, b = rng.split(':')
    x = df[(df['日期'] >= a) & (df['日期'] <= b)]
    n = x['日期'].nunique()
    if n == 0: raise SystemExit('区间 %s 没有数据' % rng)
    s = x[COLS].sum()
    return {k: float(s[k]) / n * days for k in COLS}, n

def ratios(m):
    g = lambda a, b: m[a] / m[b] if m[b] else None
    return {'tacos': g('广告花费', '销售额'), 'acos': g('广告花费', '广告销售额'), 'roas_ad': g('广告销售额', '广告花费'),
            'roas_total': g('销售额', '广告花费'), 'ctr': g('点击', '展示'), 'cpc': g('广告花费', '点击'),
            'ad_cvr': g('广告订单量', '点击'), 'aov': g('销售额', '订单量'), 'order_gp_rate': g('订单毛利润', '销售额'),
            'settled_gp_rate': g('结算毛利润', '销售额'), 'ad_order_share': g('广告订单量', '订单量')}

def actual(df, pre_rng, post_rng, cm=None, plan_res=None, plan_map=None):
    pre, n1 = window(df, pre_rng); post, n2 = window(df, post_rng)
    d = {k: post[k] - pre[k] for k in COLS}
    types = []
    for t in TYPES:
        sp, ad, od = d[t + '广告费'], d[t + '广告销售额'], d[t + '广告订单量']
        if abs(sp) < 1 and abs(od) < 0.5: continue
        types.append({'type': t, 'spend': sp, 'ad_sales': ad, 'ad_orders': od,
                      'cpo': sp / od if od else None, 'roas': ad / sp if sp else None,
                      'pre_acos': pre[t + '广告费'] / pre[t + '广告销售额'] if pre[t + '广告销售额'] else None,
                      'post_acos': post[t + '广告费'] / post[t + '广告销售额'] if post[t + '广告销售额'] else None})
    res = {'days': {'pre': n1, 'post': n2}, 'monthly_pre': pre, 'monthly_post': post, 'delta': d,
           'ratios_pre': ratios(pre), 'ratios_post': ratios(post), 'by_type': types,
           'attribution': {'all_orders': d['订单量'], 'ad_orders': d['广告订单量'], 'organic_orders': d['订单量'] - d['广告订单量']},
           'profit': {'order_gp_delta': d['订单毛利润'],
                      'order_gp_per_incremental_order': d['订单毛利润'] / d['订单量'] if d['订单量'] else None,
                      'order_gp_margin_on_incremental_sales': d['订单毛利润'] / d['销售额'] if d['销售额'] else None}}
    if cm is not None:
        ad_profit = d['广告销售额'] * cm - d['广告花费']
        res['profit'].update({'ad_attributed_profit': ad_profit,
                              'ad_profit_per_order': ad_profit / d['广告订单量'] if d['广告订单量'] else None,
                              'ad_marginal_margin': ad_profit / d['广告销售额'] if d['广告销售额'] else None,
                              'all_profit_cm_method': d['销售额'] * cm - d['广告花费']})
    if plan_res:
        res['vs_plan'] = compare(plan_res, res, plan_map or {})
    return res

def compare(p, a, plan_map):
    """plan_map: 方案 lever 名 → 实际广告类型列表，如 {"SP加投":["SP"],"CTR优化":["SP"],"SBV新增":["SBV"]}"""
    act = {t['type']: t for t in a['by_type']}
    rows, used = {}, set()
    for lv in p['levers']:
        types = plan_map.get(lv['name'], [])
        key = '+'.join(types) if types else lv['name']
        r = rows.setdefault(key, {'name': key, 'plan_levers': [], 'plan_spend': 0, 'plan_orders': 0, 'plan_sales': 0, 'types': types})
        r['plan_levers'].append(lv['name']); r['plan_spend'] += lv['spend']; r['plan_orders'] += lv['orders']; r['plan_sales'] += lv['sales']
        used.update(types)
    for t in act:
        if t not in used: rows[t] = {'name': t + '（方案外）', 'plan_levers': [], 'plan_spend': 0, 'plan_orders': 0, 'plan_sales': 0, 'types': [t]}
    out = []
    for r in rows.values():
        ts = [act[t] for t in r['types'] if t in act]
        r['actual_spend'] = sum(t['spend'] for t in ts); r['actual_orders'] = sum(t['ad_orders'] for t in ts); r['actual_ad_sales'] = sum(t['ad_sales'] for t in ts)
        r['spend_dev_pct'] = (r['actual_spend'] / r['plan_spend'] - 1) * 100 if r['plan_spend'] else None
        r['orders_dev_pct'] = (r['actual_orders'] / r['plan_orders'] - 1) * 100 if r['plan_orders'] else None
        r['plan_cpo'] = r['plan_spend'] / r['plan_orders'] if r['plan_orders'] else None
        r['actual_cpo'] = r['actual_spend'] / r['actual_orders'] if r['actual_orders'] else None
        r['plan_roas'] = r['plan_sales'] / r['plan_spend'] if r['plan_spend'] else None
        r['actual_roas'] = r['actual_ad_sales'] / r['actual_spend'] if r['actual_spend'] else None
        out.append(r)
    d = a['delta']
    return {'levers': out,
            'total': {'plan_spend': p['total']['spend'], 'actual_spend': d['广告花费'],
                      'plan_orders': p['total']['orders'], 'actual_ad_orders': d['广告订单量'], 'actual_all_orders': d['订单量'],
                      'plan_roas': p['incremental']['roas'], 'actual_roas': d['广告销售额'] / d['广告花费'] if d['广告花费'] else None,
                      'plan_cpo': p['incremental']['cpo'], 'actual_cpo': d['广告花费'] / d['广告订单量'] if d['广告订单量'] else None,
                      'plan_tacos_pt': p['delta']['tacos_pt'],
                      'actual_tacos_pt': (a['ratios_post']['tacos'] - a['ratios_pre']['tacos']) * 100,
                      'plan_profit': p['incremental']['profit'], 'actual_ad_profit': a['profit'].get('ad_attributed_profit'),
                      'plan_profit_per_order': p['incremental']['profit_per_order'], 'actual_ad_profit_per_order': a['profit'].get('ad_profit_per_order'),
                      'plan_marginal_margin': p['incremental']['marginal_margin'], 'actual_ad_marginal_margin': a['profit'].get('ad_marginal_margin')}}

# ---------------------------------------------------------------- cli
def clean(o):
    if isinstance(o, float): return None if math.isnan(o) or math.isinf(o) else round(o, 4)
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    return o

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p1 = sub.add_parser('plan'); p1.add_argument('--config', required=True); p1.add_argument('--out')
    p2 = sub.add_parser('actual'); p2.add_argument('--data', required=True); p2.add_argument('--pre', required=True); p2.add_argument('--post', required=True)
    p2.add_argument('--country'); p2.add_argument('--match', action='append'); p2.add_argument('--plan'); p2.add_argument('--cm', type=float); p2.add_argument('--out')
    a = ap.parse_args()
    if a.cmd == 'plan':
        res = plan(json.load(open(a.config, encoding='utf-8')))
    else:
        cfg = json.load(open(a.plan, encoding='utf-8')) if a.plan else None
        pres = plan(cfg) if cfg else None
        cm = a.cm if a.cm is not None else (pres['contribution_margin'] if pres else None)
        res = actual(load(a.data, a.country, a.match), a.pre, a.post, cm, pres, (cfg or {}).get('actual_type_map'))
        if pres: res['plan'] = pres
    s = json.dumps(clean(res), ensure_ascii=False, indent=1)
    if a.out: open(a.out, 'w', encoding='utf-8').write(s)
    print(s)

if __name__ == '__main__':
    main()
