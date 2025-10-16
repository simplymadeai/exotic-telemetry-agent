# api/app.py
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import duckdb, os, json, datetime, traceback
import pandas as pd
from datetime import datetime as dt, timedelta, timezone

# Local modules
from anomaly import find_anomalies
from rca import rank_root_causes
from remediation import apply_remediation

DB_PATH = os.getenv("RCA_DB", "rca.duckdb")
print("DB path:", os.path.abspath(DB_PATH))

# ---------- DB setup ----------
con = duckdb.connect(DB_PATH)

# Canonical 11-column schema (includes inlet_temp_c, vcore_v)
con.execute("""
CREATE TABLE IF NOT EXISTS telemetry (
    ts TIMESTAMP,
    device_id VARCHAR,
    inlet_temp_c DOUBLE,
    fan_rpm INTEGER,
    temp_c DOUBLE,
    vcore_v DOUBLE,
    cpu_pct DOUBLE,
    mem_pct DOUBLE,
    disk_errors INTEGER,
    nic_drops INTEGER,
    latency_ms DOUBLE
)
""")

con.execute("""
CREATE TABLE IF NOT EXISTS actions (
    ts TIMESTAMP,
    device_id VARCHAR,
    action VARCHAR,
    params VARCHAR
)
""")

# ---------- FastAPI ----------
app = FastAPI(title="Exotic Telemetry Agent API")

@app.get("/health")
def health():
    return {"status": "ok"}

# ---------- Ingest (hardened: guarantees non-null UTC timestamps) ----------
@app.post("/ingest")
async def ingest(request: Request):
    """
    Accept single event or list of events; insert by named columns.
    If timestamp is missing/invalid, set to current UTC so time windows work.
    """
    payload = await request.json()
    events = payload if isinstance(payload, list) else [payload]

    df = pd.DataFrame(events)

    # Parse/normalize timestamp; coerce invalid to NaT
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
    else:
        df["ts"] = pd.NaT

    # Fill NaT timestamps with current UTC
    now_utc = pd.Timestamp.utcnow()
    df["ts"] = df["ts"].fillna(now_utc)

    # Ensure required columns exist (backfill missing ones with None)
    required = [
        "ts","device_id","inlet_temp_c","fan_rpm","temp_c","vcore_v",
        "cpu_pct","mem_pct","disk_errors","nic_drops","latency_ms"
    ]
    for col in required:
        if col not in df.columns:
            df[col] = None

    before = con.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
    con.execute("""
        INSERT INTO telemetry
        (ts, device_id, inlet_temp_c, fan_rpm, temp_c, vcore_v,
         cpu_pct, mem_pct, disk_errors, nic_drops, latency_ms)
        SELECT ts, device_id, inlet_temp_c, fan_rpm, temp_c, vcore_v,
               cpu_pct, mem_pct, disk_errors, nic_drops, latency_ms
        FROM df
    """)
    after = con.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
    print(f"[INGEST] inserted={after - before}  total={after}")

    return {"ingested": len(df)}

# ---------- Basic queries ----------
@app.get("/devices")
def devices():
    rows = con.execute("SELECT DISTINCT device_id FROM telemetry ORDER BY device_id").fetchall()
    return {"devices": [r[0] for r in rows]}

class WindowReq(BaseModel):
    device_id: str
    start: str   # ISO string
    end: str     # ISO string

@app.post("/window")
def window(req: WindowReq):
    df = con.execute(
        """
        SELECT *
        FROM telemetry
        WHERE device_id = ?
          AND ts BETWEEN CAST(? AS TIMESTAMP) AND CAST(? AS TIMESTAMP)
        ORDER BY ts ASC
        """,
        [req.device_id, req.start, req.end],
    ).df()
    return {"rows": json.loads(df.to_json(orient="records", date_format="iso"))}

# ---------- Time-based latest window (server clock) ----------
@app.get("/latest")
def latest(device_id: str, minutes: int = 10, limit: int = 5000):
    start = (dt.utcnow() - timedelta(minutes=int(minutes))).isoformat() + "Z"
    df = con.execute(
        """
        SELECT *
        FROM telemetry
        WHERE device_id = ?
          AND ts BETWEEN CAST(? AS TIMESTAMP) AND CURRENT_TIMESTAMP
        ORDER BY ts ASC
        LIMIT ?
        """,
        [device_id, start, limit],
    ).df()
    return {"rows": json.loads(df.to_json(orient="records", date_format="iso"))}

# ---------- Time-agnostic recent rows (ignores clock; great for charts) ----------
@app.get("/latest_recent")
def latest_recent(device_id: str, limit: int = 1000):
    df = con.execute(
        """
        SELECT *
        FROM telemetry
        WHERE device_id = ?
        ORDER BY ts DESC
        LIMIT ?
        """,
        [device_id, limit],
    ).df()
    df = df.sort_values("ts")
    return {"rows": json.loads(df.to_json(orient="records", date_format="iso"))}

# ---------- Quick debug helpers ----------
@app.get("/rowcount")
def rowcount():
    total = con.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
    return {"rows": int(total)}

@app.get("/stats")
def stats(minutes: int = 60):
    start = (dt.utcnow() - timedelta(minutes=int(minutes))).isoformat() + "Z"
    df = con.execute(
        """
        SELECT device_id, COUNT(*) AS rows
        FROM telemetry
        WHERE ts BETWEEN CAST(? AS TIMESTAMP) AND CURRENT_TIMESTAMP
        GROUP BY 1
        ORDER BY 2 DESC
        """,
        [start],
    ).df()
    return {"minutes": minutes, "devices": json.loads(df.to_json(orient="records"))}

@app.get("/stats_null")
def stats_null():
    """Counts of NULL/non-NULL ts rows."""
    nulls = con.execute("SELECT COUNT(*) FROM telemetry WHERE ts IS NULL").fetchone()[0]
    not_nulls = con.execute("SELECT COUNT(*) FROM telemetry WHERE ts IS NOT NULL").fetchone()[0]
    return {"ts_null": int(nulls), "ts_not_null": int(not_nulls)}

@app.get("/last")
def last(device_id: str, limit: int = 10):
    df = con.execute(
        """
        SELECT *
        FROM telemetry
        WHERE device_id = ?
        ORDER BY ts DESC
        LIMIT ?
        """,
        [device_id, limit],
    ).df()
    return {"rows": json.loads(df.to_json(orient="records", date_format="iso"))}

# ---------- Anomaly + RCA ----------
@app.post("/anomaly/window")
def anomaly_window(req: WindowReq):
    df = con.execute(
        """
        SELECT *
        FROM telemetry
        WHERE device_id = ?
          AND ts BETWEEN CAST(? AS TIMESTAMP) AND CAST(? AS TIMESTAMP)
        ORDER BY ts ASC
        """,
        [req.device_id, req.start, req.end],
    ).df()
    anomalies = find_anomalies(df)
    return {"anomalies": anomalies}

@app.post("/rca")
def rca(req: WindowReq):
    df = con.execute(
        """
        SELECT *
        FROM telemetry
        WHERE device_id = ?
          AND ts BETWEEN CAST(? AS TIMESTAMP) AND CAST(? AS TIMESTAMP)
        ORDER BY ts ASC
        """,
        [req.device_id, req.start, req.end],
    ).df()
    anomalies = find_anomalies(df)
    result = rank_root_causes(df, anomalies)
    return result

@app.get("/detect_latest")
def detect_latest(device_id: str, minutes: int = 10):
    """
    Run anomaly + RCA over the last N minutes (server clock).
    """
    try:
        start = (dt.utcnow() - timedelta(minutes=int(minutes))).isoformat() + "Z"
        df = con.execute(
            """
            SELECT *
            FROM telemetry
            WHERE device_id = ?
              AND ts BETWEEN CAST(? AS TIMESTAMP) AND CURRENT_TIMESTAMP
            ORDER BY ts ASC
            """,
            [device_id, start],
        ).df()
        anomalies = find_anomalies(df)
        result = rank_root_causes(df, anomalies)
        return {"anomalies": anomalies, "rca": result}
    except Exception as e:
        print("[/detect_latest ERROR]", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"detect_latest failed: {e}")

# ---------- Remediation ----------
class RemediationReq(BaseModel):
    device_id: str
    action: str
    params: Dict[str, Any] = {}

@app.post("/remediate")
def remediate(req: RemediationReq):
    """
    Uses CURRENT_TIMESTAMP (SQL) to avoid string→TIMESTAMP cast issues.
    """
    try:
        params_json = json.dumps(req.params) if req.params is not None else "{}"
        con.execute(
            """
            INSERT INTO actions (ts, device_id, action, params)
            VALUES (CURRENT_TIMESTAMP, ?, ?, ?)
            """,
            [req.device_id, req.action, params_json],
        )
        row = con.execute(
            """
            SELECT ts, device_id, action, params
            FROM actions
            WHERE device_id = ?
            ORDER BY ts DESC
            LIMIT 1
            """,
            [req.device_id],
        ).fetchone()
        ts_iso = row[0].isoformat() + "Z" if hasattr(row[0], "isoformat") else str(row[0])
        return {"ok": True, "ts": ts_iso, "device_id": row[1], "action": row[2],
                "params": json.loads(row[3]) if row[3] else {}}
    except Exception as e:
        print("[/remediate ERROR]", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"remediate failed: {e}")

@app.get("/actions")
def list_actions():
    rows = con.execute(
        "SELECT ts, device_id, action, params FROM actions ORDER BY ts DESC LIMIT 100"
    ).fetchall()
    out = []
    for r in rows:
        ts_iso = r[0].isoformat() + "Z" if hasattr(r[0], "isoformat") else str(r[0])
        try:
            pj = json.loads(r[3]) if r[3] else {}
        except Exception:
            pj = {}
        out.append({"ts": ts_iso, "device_id": r[1], "action": r[2], "params": pj})
    return {"actions": out}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
