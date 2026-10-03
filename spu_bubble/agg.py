import pandas as pd, json, openpyxl, re
SRC='/root/.claude/uploads/e2b0cf22-9374-538f-b574-2ff3b36ec7bf/912001fb-____-ASIN-____-2106354034537455618.xlsx'
OUT='/home/user/claude-/spu_bubble/'
# 型号合并规则：左边的型号并入右边（用户确认为同一产品）
MERGE={'得伟-电源逆变器-200W,得伟-电源逆变器-200W-美规-黄色':'得伟-电源逆变器-200W'}
x=pd.ExcelFile(SRC); q=x.parse('销量'); s=x.parse('销售额'); o=x.parse('订单量')
df=q[['ASIN','型号','三级分类','国家','小计']].rename(columns={'小计':'销量'})
df['销售额']=s['小计']; df['订单量']=o['小计']
# 增长率：近3月(7-9月) 对比 前3月(4-6月)，10月不完整不计入
df['前3月']=q[['2026-04','2026-05','2026-06']].sum(axis=1); df['近3月']=q[['2026-07','2026-08','2026-09']].sum(axis=1)
df['型号']=df['型号'].fillna('(未填型号)').replace(MERGE); df['三级分类']=df['三级分类'].fillna('(未分类)')
cat=df.groupby(['型号','三级分类'])['销量'].sum().reset_index().sort_values('销量',ascending=False).drop_duplicates('型号').set_index('型号')['三级分类']
m=df.groupby('型号').agg(销量=('销量','sum'),销售额=('销售额','sum'),订单量=('订单量','sum'),链接数=('ASIN','nunique'),站点数=('国家','nunique'),前3月=('前3月','sum'),近3月=('近3月','sum')).reset_index()
m['三级分类']=m['型号'].map(cat)
c=df.groupby('三级分类').agg(销量=('销量','sum'),销售额=('销售额','sum'),订单量=('订单量','sum'),型号数=('型号','nunique'),链接数=('ASIN','nunique'),前3月=('前3月','sum'),近3月=('近3月','sum')).reset_index()
for t in (m,c): t['均价']=(t['销售额']/t['销量']).round(2)
m=m.sort_values('销量',ascending=False); c=c.sort_values('销量',ascending=False)
for t in (m,c):
  t['销量占比']=(t['销量']/t['销量'].sum()).round(4)
  t['增长率']=(t['近3月']/t['前3月']-1).where(t['前3月']>0).round(4)
# 象限：销售额中位数 + 增长率 0% 切分。型号按销量 Top 60（与页面默认一致），分类按全部
TOPN=60
def quad(t):
  med=t['销售额'].median(); hi=t['销售额']>=med; up=(t['增长率']>=0)|t['增长率'].isna()&(t['近3月']>0)
  return pd.Series(['明星' if h and u else '金牛' if h else '问题' if u else '瘦狗' for h,u in zip(hi,up)],index=t.index)
m['象限']=''; m.iloc[:TOPN,m.columns.get_loc('象限')]=quad(m.iloc[:TOPN]); c['象限']=quad(c)
m.to_csv('m.csv',index=False)
mc=m[['型号','三级分类','象限','销量','销量占比','前3月','近3月','增长率','订单量','销售额','均价','链接数','站点数']].rename(columns={'销售额':'销售额 (USD)','均价':'均价 (USD)','象限':'象限 (Top60口径)'})
cc=c[['三级分类','象限','销量','销量占比','前3月','近3月','增长率','订单量','销售额','均价','型号数','链接数']].rename(columns={'销售额':'销售额 (USD)','均价':'均价 (USD)'})
with pd.ExcelWriter(OUT+'SPU销量汇总.xlsx') as w:
  mc.to_excel(w,sheet_name='按产品型号',index=False); cc.to_excel(w,sheet_name='按三级分类',index=False)
  # 近3个月(7-9月)比前3个月(4-6月)下跌超过30%的型号，全部型号口径，新品(4-6月无销量)不计
  d=m[m['增长率']<-0.3].copy(); d['减少件数']=d['前3月']-d['近3月']; d=d.sort_values('减少件数',ascending=False)
  d[['型号','三级分类','前3月','近3月','增长率','减少件数','销量','销售额','链接数','站点数']].rename(columns={'前3月':'4-6月销量','近3月':'7-9月销量','销量':'1-10月销量','销售额':'销售额 (USD)'}).to_excel(w,sheet_name='近3月下跌超30%-型号',index=False)
  dc=d.groupby('三级分类').agg(下跌型号数=('型号','count'),前3月=('前3月','sum'),近3月=('近3月','sum')).reset_index()
  dc['增长率']=(dc['近3月']/dc['前3月']-1).round(4); dc['减少件数']=dc['前3月']-dc['近3月']; dc['占下跌总量']=(dc['减少件数']/dc['减少件数'].sum()).round(4)
  dc=dc.sort_values('减少件数',ascending=False)
  tot=pd.DataFrame([{'三级分类':'合计','下跌型号数':dc['下跌型号数'].sum(),'前3月':dc['前3月'].sum(),'近3月':dc['近3月'].sum(),'增长率':round(dc['近3月'].sum()/dc['前3月'].sum()-1,4),'减少件数':dc['减少件数'].sum(),'占下跌总量':1.0}])
  pd.concat([dc,tot]).rename(columns={'前3月':'4-6月销量','近3月':'7-9月销量'}).to_excel(w,sheet_name='近3月下跌超30%-分类汇总',index=False)
wb=openpyxl.load_workbook(OUT+'SPU销量汇总.xlsx')
for ws in wb:
  for col in ws.iter_cols(min_row=1):
    if 'USD' in str(col[0].value):
      for cl in col[1:]: cl.number_format='$#,##0.00'
    if col[0].value in('销量占比','增长率','占下跌总量'):
      for cl in col[1:]: cl.number_format='0.00%'
for ws in wb:
  ws.freeze_panes='A2'
  for col in ws.columns:
    ws.column_dimensions[col[0].column_letter].width=max(10,min(48,max(len(str(c.value or ''))*1.6 for c in col[:200])))
wb.save(OUT+'SPU销量汇总.xlsx')
r=lambda v: round(float(v),2)
data={'m':[[a,b,int(v),r(sa),int(n),int(st),int(p),int(l)] for a,b,v,sa,n,st,p,l in m[['型号','三级分类','销量','销售额','链接数','站点数','前3月','近3月']].values],
      'c':[[a,int(v),r(sa),int(k),int(n),int(p),int(l)] for a,v,sa,k,n,p,l in c[['三级分类','销量','销售额','型号数','链接数','前3月','近3月']].values]}
h=OUT+'SPU销量气泡图.html'; page=open(h).read()
page=re.sub(r'const DATA = .*?;\n','const DATA = '+json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('\\','\\\\')+';\n',page,count=1,flags=re.S)
open(h,'w').write(page)
print(len(m), m.head(8)[['型号','销量','销售额','前3月','近3月','增长率','象限']].to_string()); print(c.head(8)[['三级分类','销量','增长率','象限']].to_string()); print(m['象限'].value_counts()); print((m['前3月']==0).sum(), ((m['前3月']==0)&(m['近3月']>0)).sum())
