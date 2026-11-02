# per-unit economics; constants flagged as assumptions where not from ops plan
C={ # landed, fba, refund, inventory
 'B0HG9L16S7':dict(landed=18.12,fba=6.99,rf=.069,inv=6832,store=.40),
 'B0FW9V5S3W':dict(landed=12.28,fba=6.39,rf=.08,inv=5737,store=.30),   # 暂估: 按 GY8 同档
 'B0GQYW1R46':dict(landed=16.81,fba=6.99,rf=.076,inv=1532,store=.65),
 'B0GY8SCGC3':dict(landed=12.28,fba=6.39,rf=.136,inv=1305,store=.32)}
AMZ_COMM=.15; PROMO=.02; TK_FEE=.08; TK_AFF=.15; MCF=10.5; TM_3PL=9.0; REMOVAL=2.0
plan={ # channel: (units, price, tacos)
 'B0HG9L16S7':{'amazon':(2100,44.99,.20),'tiktok':(900,49.99,0),'temu':(300,39.0,0),'b2b':(2200,21.81,0)},
 'B0FW9V5S3W':{'amazon':(1500,34.99,.15),'tiktok':(600,44.99,0),'temu':(400,33.0,0),'b2b':(2100,14.70,0)},
 'B0GQYW1R46':{'amazon':(700,44.99,.20),'tiktok':(250,49.99,0),'temu':(280,39.0,0),'b2b':(0,20.20,0)},
 'B0GY8SCGC3':{'amazon':(800,34.19,.15),'tiktok':(0,39.99,0),'temu':(250,30.0,0),'b2b':(0,14.70,0)}}
def cash(a,ch,p,t):
    c=C[a]
    if ch=='amazon': return p*(1-AMZ_COMM-c['rf']-PROMO)-c['fba']-p*t
    if ch=='tiktok': return p*(1-TK_FEE-TK_AFF-c['rf'])-MCF
    if ch=='temu': return p*(1-c['rf']*0.6)-REMOVAL-TM_3PL
    if ch=='b2b': return p-REMOVAL
tot_u=tot_cash=tot_pnl=0
for a,chs in plan.items():
    for ch,(u,p,t) in chs.items():
        cu=cash(a,ch,p,t); pl=cu-C[a]['landed']-(C[a]['store'] if ch=='amazon' else 0)
        print(f'{a} {ch:7s} u={u:5d} p={p:6.2f} cash/u={cu:6.2f} pnl/u={pl:6.2f} cash={cu*u:9.0f} pnl={pl*u:9.0f}')
        tot_u+=u; tot_cash+=cu*u; tot_pnl+=pl*u
inv=sum(c['inv'] for c in C.values())
print('total',tot_u,round(tot_u/inv,3),round(tot_cash),round(tot_pnl))
# ops check HG9 46.32 tacos .30
print('ops check HG9', round(cash('B0HG9L16S7','amazon',46.32,.30)-18.12-.40,2))
# breakeven tacos vs wholesale for HG9 at 44.99/49.99
for p in (39.99,44.99,49.99):
    c=C['B0HG9L16S7']; base=p*(1-AMZ_COMM-c['rf']-PROMO)-c['fba']
    print('HG9 price',p,'tacos where amazon cash = wholesale net 19.81:',round((base-19.81)/p,3))

print('------ scenarios')
C['B0FW9V5S3W']['landed']=14.00
TK_AFF=.20
def pnl(a,ch,u,p,t):
    cu=cash(a,ch,p,t); return u, cu*u, (cu-C[a]['landed']-(C[a]['store'] if ch=='amazon' else 0))*u
def run(pl):
    U=Ca=P=0
    for a,chs in pl.items():
        for ch,(u,p,t) in chs.items():
            x=pnl(a,ch,u,p,t); U+=x[0]; Ca+=x[1]; P+=x[2]
    return U,round(U/inv,3),round(Ca),round(P)
print('final',run(plan))
import copy
pes=copy.deepcopy(plan)
for a,chs in pes.items():
    short=0
    for ch in ('amazon','tiktok','temu'):
        u,p,t=chs[ch]; nu=round(u*.6); short+=u-nu; chs[ch]=(nu,p,t)
    u,p,t=chs['b2b']; chs['b2b']=(u+short,p,t)
print('pessimistic->b2b',run(pes))
ops={'B0HG9L16S7':{'amazon':(1710,46.32,None)},'B0GQYW1R46':{'amazon':(750,44.99,.25)},'B0GY8SCGC3':{'amazon':(1225,34.19,.15)},'B0FW9V5S3W':{'amazon':(990,39.99,.214)}}
# HG9 ops tacos by month 30/30/25 weighted
U=Ca=P=0
for a,chs in ops.items():
    u,p,t=chs['amazon']
    if a=='B0HG9L16S7':
        for uu,tt in ((450,.30),(600,.30),(660,.25)):
            x=pnl(a,'amazon',uu,p,tt); U+=x[0];Ca+=x[1];P+=x[2]
    else:
        x=pnl(a,'amazon',u,p,t); U+=x[0];Ca+=x[1];P+=x[2]
    print(a,round(P))
print('ops',U,round(U/inv,3),round(Ca),round(P))
