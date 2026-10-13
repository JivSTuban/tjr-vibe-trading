"""Copycat/crowding test: does launching first on a topic beat launching later?

Usage: uv run python -W ignore backtesting/memecoin_copycat/analysis.py <ticker|name> tokens.csv

Why two tables: the CAUSAL one uses only what is knowable at launch (how many other
deployers already launched this key in the 1h chain). The HINDSIGHT one conditions on
the cluster later becoming hot, which is look-ahead (copies launch BECAUSE the original
ran), so it is an upper bound and must not be quoted as an edge.
"""
import re, sys, pandas as pd, numpy as np
CSV=sys.argv[2]  # extract produced by the SQL in FINDINGS.md
d=pd.read_csv(CSV)
d=d[d.peak_liq.notna()].copy()
d['t']=pd.to_datetime(d.created_at,utc=True,format='ISO8601')
d=d.sort_values('t').reset_index(drop=True)
# pair-flip guard: liquidity above market cap or absurd = corrupted read (trap-pair-flip)
clean=(d.peak_liq<=d.peak_mc.fillna(0)*1.0)&(d.peak_liq<10e6)
d['win_raw']=d.peak_liq>=15000
d['win']=d.win_raw&clean
print(f"tokens {len(d):,}  win_raw {d.win_raw.mean():.4%} ({d.win_raw.sum():,})  win_clean {d.win.mean():.4%} ({d.win.sum():,})")
print("median peak liq", round(d.peak_liq.median()))
def norm(s):
    s=str(s).lower(); s=re.sub(r'[^a-z0-9]+','',s); return s
KEY=sys.argv[1]
d=d[d[KEY].notna()].copy()
d['key']=d[KEY].map(norm)
d=d[d.key.str.len()>=3]
GAP=pd.Timedelta(hours=1)
# chain clusters: same key, gap < 1h between consecutive launches
d=d.sort_values(['key','t'])
d['gapnew']=(d.groupby('key').t.diff()>GAP)|d.key.ne(d.key.shift())
d['cid']=d.gapnew.cumsum()
g=d.groupby('cid')
d['csize']=g.mint.transform('size')
d['cdep']=g.deployer.transform('nunique')
# rank by first launch per deployer within cluster (dedupes serial spam)
d['dep_first']=~d.duplicated(['cid','deployer'])
dd=d[d.dep_first].copy()
dd['rank']=dd.groupby('cid').cumcount()+1
dd['n_dep']=dd.groupby('cid').deployer.transform('size')
print("\nkey:",KEY,"| clusters",dd.cid.nunique(),"| tokens after dedupe",len(dd))
# ---- causal: how many distinct deployers already launched this key in the cluster before me
def bucket(r):
    return '1st' if r==1 else '2-3' if r<=3 else '4-10' if r<=10 else '11-30' if r<=30 else '31+'
dd['rb']=dd['rank'].map(bucket)
order=['1st','2-3','4-10','11-30','31+']
print("\nCAUSAL (rank known at launch): win rate by how many others launched the key before you, in this 1h-chain")
t=dd.groupby('rb').agg(n=('win','size'),win=('win','mean'),med_liq=('peak_liq','median')).reindex(order)
t['win']=(t.win*100).round(2); print(t.to_string())
# ---- hindsight: clusters that became hot (>=8 distinct deployers)
hot=dd[dd.n_dep>=8]
print("\nHINDSIGHT hot clusters (>=8 deployers):",hot.cid.nunique(),"clusters,",len(hot),"tokens")
t=hot.groupby('rb').agg(n=('win','size'),win=('win','mean'),med_liq=('peak_liq','median')).reindex(order)
t['win']=(t.win*100).round(2); print(t.to_string())
# who wins inside hot clusters
w=hot[hot.win]
cl_with=w.cid.nunique()
print(f"hot clusters with >=1 winner: {cl_with} / {hot.cid.nunique()} = {cl_with/hot.cid.nunique():.1%}")
fw=w.sort_values('rank').groupby('cid').first()
print("rank of FIRST winner in those clusters:\n",fw['rank'].map(bucket).value_counts(normalize=True).reindex(order).round(3).to_string())
# expected share if rank were irrelevant: share of tokens in each bucket
print("share of hot-cluster tokens by bucket:\n",hot.rb.value_counts(normalize=True).reindex(order).round(3).to_string())
# is 1st launcher of a hot cluster better than 1st of cold?
cold1=dd[(dd.n_dep<3)&(dd['rank']==1)]
print(f"\nbaseline: 1st of cold clusters (<3 deployers) win {cold1.win.mean():.2%} n={len(cold1):,}")
hot1=hot[hot['rank']==1]
print(f"1st of hot clusters win {hot1.win.mean():.2%} n={len(hot1):,}")
top=hot.groupby('cid').agg(key=('key','first'),n_dep=('n_dep','first'),wins=('win','sum'),best=('peak_liq','max')).sort_values('n_dep',ascending=False).head(12)
print("\nlargest clusters:\n",top.to_string())
