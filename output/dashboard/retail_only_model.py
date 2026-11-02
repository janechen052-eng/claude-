exec(open('econ.py').read().split("print('------ scenarios')")[0].split('tot_u=tot_cash')[0])
C['B0FW9V5S3W']['landed']=14.00
TK_AFF=.20
plan={
 'B0HG9L16S7':{'amazon':(2700,41.99,.18),'tiktok':(1400,44.99,0),'temu':(700,36.0,0)},
 'B0FW9V5S3W':{'amazon':(2000,32.99,.12),'tiktok':(900,39.99,0),'temu':(700,30.0,0)},
 'B0GQYW1R46':{'amazon':(700,44.99,.20),'tiktok':(250,49.99,0),'temu':(280,39.0,0)},
 'B0GY8SCGC3':{'amazon':(800,34.19,.15),'tiktok':(0,39.99,0),'temu':(250,30.0,0)}}
inv=sum(c['inv'] for c in C.values())
def run(pl,f=1):
    U=Ca=P=0
    for a,chs in pl.items():
        au=0
        for ch,(u,p,t) in chs.items():
            u=round(u*f); cu=cash(a,ch,p,t); pl_=cu-C[a]['landed']-(C[a]['store'] if ch=='amazon' else 0)
            U+=u;Ca+=cu*u;P+=pl_*u; au+=u
            if f==1: print(a,ch,u,p,round(cu,2),round(pl_,2))
        if f==1: print('  ',a,au,round(au/C[a]['inv'],3))
    return U,round(U/inv,3),round(Ca),round(P)
print('final',run(plan)); print('pess',run(plan,.6))
