import pandas as pd, yaml, os
DAG_PATH=os.getenv("RCA_DAG", os.path.join(os.path.dirname(__file__),"dag.yaml"))
def _load_dag():
    with open(DAG_PATH,"r") as f: return yaml.safe_load(f)
def _pearson(a,b):
    a=pd.Series(a).astype(float); b=pd.Series(b).astype(float)
    if a.std()==0 or b.std()==0: return 0.0
    c=a.corr(b); return float(c) if not pd.isna(c) else 0.0
def _is_upstream(u,v,parents):
    seen=set(); stack=[v]
    while stack:
        cur=stack.pop()
        for p in parents.get(cur,[]):
            if p==u: return True
            if p not in seen: seen.add(p); stack.append(p)
    return False
def rank_root_causes(df, anomalies):
    if df.empty: return {"ranked":[], "explanations":[]}
    dag=_load_dag(); nodes=dag.get("nodes",[]); edges=dag.get("edges",[])
    parents={n:[] for n in nodes}
    for src,dst in edges: parents[dst].append(src)
    symptom="latency_ms" if "latency_ms" in nodes else nodes[-1]
    anomaly_by_metric={}
    for a in anomalies: anomaly_by_metric.setdefault(a["metric"],[]).append(a["idx"])
    ranked=[]; symptom_idxs=sorted(anomaly_by_metric.get(symptom,[]))
    for m in nodes:
        if m==symptom: continue
        m_idxs=anomaly_by_metric.get(m,[])
        if not m_idxs: continue
        precedence=1.0 if (symptom_idxs and m_idxs and min(m_idxs)<min(symptom_idxs)) else 0.0
        corr=_pearson(df[m].values, df[symptom].values) if (m in df.columns and symptom in df.columns) else 0.0
        topo=1.0 if _is_upstream(m, symptom, parents) else 0.0
        score=0.5*abs(corr)+0.3*precedence+0.2*topo
        expl=[]; 
        if precedence: expl.append("upstream anomalies occur earlier than symptom")
        expl.append(f"corr({m}, {symptom})≈{corr:.2f}")
        if topo: expl.append("upstream in dependency DAG")
        ranked.append({"metric":m,"score":float(score),"explanation":expl})
    ranked.sort(key=lambda x:x["score"], reverse=True)
    return {"ranked": ranked[:5], "explanations": ranked[:5]}
