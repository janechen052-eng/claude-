import pandas as pd, json, openpyxl, re
SRC='/root/.claude/uploads/e2b0cf22-9374-538f-b574-2ff3b36ec7bf/912001fb-____-ASIN-____-2106354034537455618.xlsx'
OUT='/home/user/claude-/spu_bubble/'
# 型号合并规则：左边的型号并入右边（用户确认为同一产品）
MERGE={'得伟-电源逆变器-200W,得伟-电源逆变器-200W-美规-黄色':'得伟-电源逆变器-200W'}
x=pd.ExcelFile(SRC); q=x.parse('销量'); s=x.parse('销售额'); o=x.parse('订单量')
df=q[['ASIN','型号','三级分类','国家','小计']].rename(columns={'小计':'销量'})
df['销售额']=s['小计']; df['订单量']=o['小计']
df['型号']=df['型号'].fillna('(未填型号)').replace(MERGE); df['三级分类']=df['三级分类'].fillna('(未分类)')
cat=df.groupby(['型号','三级分类'])['销量'].sum().reset_index().sort_values('销量',ascending=False).drop_duplicates('型号').set_index('型号')['三级分类']
m=df.groupby('型号').agg(销量=('销量','sum'),销售额=('销售额','sum'),订单量=('订单量','sum'),链接数=('ASIN','nunique'),站点数=('国家','nunique')).reset_index()
m['三级分类']=m['型号'].map(cat)
c=df.groupby('三级分类').agg(销量=('销量','sum'),销售额=('销售额','sum'),订单量=('订单量','sum'),型号数=('型号','nunique'),链接数=('ASIN','nunique')).reset_index()
for t in (m,c): t['均价']=(t['销售额']/t['销量']).round(2)
m=m.sort_values('销量',ascending=False); c=c.sort_values('销量',ascending=False)
for t in (m,c): t['销量占比']=(t['销量']/t['销量'].sum()).round(4)
m.to_csv('m.csv',index=False)
mc=m[['型号','三级分类','销量','销量占比','订单量','销售额','均价','链接数','站点数']].rename(columns={'销售额':'销售额 (USD)','均价':'均价 (USD)'})
cc=c[['三级分类','销量','销量占比','订单量','销售额','均价','型号数','链接数']].rename(columns={'销售额':'销售额 (USD)','均价':'均价 (USD)'})
with pd.ExcelWriter(OUT+'SPU销量汇总.xlsx') as w:
  mc.to_excel(w,sheet_name='按产品型号',index=False); cc.to_excel(w,sheet_name='按三级分类',index=False)
wb=openpyxl.load_workbook(OUT+'SPU销量汇总.xlsx')
for ws in wb:
  for col in ws.iter_cols(min_row=1):
    if 'USD' in str(col[0].value):
      for cl in col[1:]: cl.number_format='$#,##0.00'
    if col[0].value=='销量占比':
      for cl in col[1:]: cl.number_format='0.00%'
wb.save(OUT+'SPU销量汇总.xlsx')
r=lambda v: round(float(v),2)
data={'m':[[a,b,int(v),r(sa),int(n),int(st)] for a,b,v,sa,n,st in m[['型号','三级分类','销量','销售额','链接数','站点数']].values],
      'c':[[a,int(v),r(sa),int(k),int(n)] for a,v,sa,k,n in c[['三级分类','销量','销售额','型号数','链接数']].values]}
h=OUT+'SPU销量气泡图.html'; page=open(h).read()
page=re.sub(r'const DATA = .*?;\n','const DATA = '+json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('\\','\\\\')+';\n',page,count=1,flags=re.S)
open(h,'w').write(page)
print(len(m), m.head(5)[['型号','销量','销售额','链接数','站点数']].to_string())
