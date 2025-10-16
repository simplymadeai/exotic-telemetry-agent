import pandas as pd, numpy as np
from sklearn.ensemble import IsolationForest
METRICS = ["cpu_pct","mem_pct","temp_c","fan_rpm","disk_errors","nic_drops","latency_ms"]
def _rolling_z(x,w=60):
    s=pd.Series(x).astype(float); mu=s.rolling(w,min_periods=10).mean(); sd=s.rolling(w,min_periods=10).std().replace(0,np.nan)
    return ((s-mu)/sd).fillna(0.0).values
def find_anomalies(df: pd.DataFrame):
    if df.empty: return []
    out=[]
    for m in METRICS:
        if m in df.columns:
            z=_rolling_z(df[m].values,w=min(60,max(10,len(df)//5)))
            for i in np.where(np.abs(z)>2.5)[0]: out.append({"idx":int(i),"ts":df.iloc[i]["ts"].isoformat(),"metric":m,"score":float(abs(z[i])),"type":"zscore"})
    X=df[METRICS].astype(float).fillna(0.0)
    if len(X)>=40:
        iso=IsolationForest(n_estimators=100,contamination=0.05,random_state=42); pred=iso.fit_predict(X); scores=-iso.score_samples(X)
        for i,p in enumerate(pred):
            if p==-1: out.append({"idx":int(i),"ts":df.iloc[i]["ts"].isoformat(),"metric":"multivariate","score":float(scores[i]),"type":"iforest"})
    keyed={}
    for a in out:
        k=(a["idx"],a["metric"])
        if k not in keyed or a["score"]>keyed[k]["score"]: keyed[k]=a
    return list(keyed.values())
