# ui/dashboard.py
import streamlit as st
import requests, datetime, time
import pandas as pd

API = "http://localhost:8000"

st.set_page_config(page_title="Exotic Telemetry Agent", layout="wide")
st.title("Exotic Telemetry Agent — Hardware↔Software Telemetry")

# ---------- Helpers ----------
def call_json(method, url, **kwargs):
    try:
        resp = requests.request(method, url, timeout=8, **kwargs)
        if not resp.ok:
            st.error(f"{method} {url} -> HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        try:
            return resp.json()
        except Exception:
            st.error(f"{method} {url} returned non-JSON:\n{resp.text[:200]}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Request error calling {url}: {e}")
        return None

def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)

def iso(dt: datetime.datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.isoformat()

def fetch_latest_recent(device, limit=2000):
    return call_json("GET", f"{API}/latest_recent", params={"device_id": device, "limit": int(limit)})

def detect_latest(device, minutes):
    return call_json("GET", f"{API}/detect_latest", params={"device_id": device, "minutes": int(minutes)})

# ---------- Health ----------
health = call_json("GET", f"{API}/health")
if not health or health.get("status") != "ok":
    st.warning("API not reachable at http://localhost:8000. Start it with `python api/app.py`.")
    st.stop()

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Time Window")
    preset = st.selectbox(
        "Window preset",
        ["Last 2 min", "Last 5 min", "Last 10 min", "Last 15 min", "Last 30 min"],
        index=2,
    )
    st.header("Auto-Refresh")
    auto_on = st.checkbox("Enable Auto-Refresh", value=True)
    interval = st.selectbox("Every (seconds)", [2, 5, 10], index=1)
    auto_detect = st.checkbox("Also run Anomaly + RCA each tick", value=False)

    preset_to_min = {"Last 2 min": 2, "Last 5 min": 5, "Last 10 min": 10, "Last 15 min": 15, "Last 30 min": 30}
    delta_min = preset_to_min[preset]

    # Labels only (server derives its own window)
    end_dt = now_utc()
    start_dt = end_dt - datetime.timedelta(minutes=delta_min)
    st.caption("Label window (server derives real window):")
    st.code(f"Start: {iso(start_dt)}\nEnd:   {iso(end_dt)}", language="text")

# ---------- Device selector (from API only) ----------
devices_json = call_json("GET", f"{API}/devices")
if not devices_json:
    st.error("Could not fetch devices from API.")
    st.stop()
devices = devices_json.get("devices", [])
if not devices:
    st.info("No devices observed yet. Start the simulator or edge agent so the API sees telemetry.")
    st.stop()
device = st.selectbox("Device (from API)", devices, index=0)

# ---------- Actions ----------
cols = st.columns([1,1,1])
with cols[0]:
    refresh_clicked = st.button("Refresh Window", type="primary")
with cols[1]:
    detect_clicked = st.button("Detect Anomalies & RCA")
with cols[2]:
    if st.button("Force Fault (drop fan target by 800)"):
        resp = call_json("POST", f"{API}/remediate", json={
            "device_id": device, "action": "Increase fan target", "params": {"fan_delta": -800}
        })
        if resp and resp.get("ok"):
            st.success("Fault injected. Watch the charts over the next ~30s.")

# ---------- Containers ----------
telemetry_container = st.container()
anomaly_container = st.container()

def render_once():
    # Telemetry: time-agnostic recent rows (always returns data if ingest works)
    data_json = fetch_latest_recent(device, limit=2000)
    with telemetry_container:
        st.subheader("Telemetry")
        if data_json and data_json.get("rows"):
            df = pd.DataFrame(data_json["rows"])
            if not df.empty:
                if df["ts"].dtype == object:
                    df["ts"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
                df = df.sort_values("ts")
                cols_order = [c for c in ["inlet_temp_c","fan_rpm","temp_c","cpu_pct","latency_ms"] if c in df.columns]
                if cols_order:
                    st.line_chart(df.set_index("ts")[cols_order])
                st.dataframe(df.tail(30), use_container_width=True)
            else:
                st.info("No rows yet.")
        else:
            st.info("No data returned. Ensure simulator/edge agent is posting to this API.")

    # Anomaly + RCA: server-side rolling window (N minutes)
    if detect_clicked or auto_detect:
        out = detect_latest(device, delta_min) or {}
        with anomaly_container:
            st.subheader("Anomalies (sample)")
            st.json({"anomalies": out.get("anomalies", [])})
            st.subheader("Top Suspected Causes")
            ranked = (out.get("rca") or {}).get("ranked", [])
            if ranked:
                for i, c in enumerate(ranked, 1):
                    st.markdown(f"**{i}. {c['metric']}** — score `{c['score']:.2f}`")
                    st.caption("Why: " + "; ".join(c.get("explanation", [])))
            else:
                st.info("No root-cause signals in this window.")

# Manual single run
if refresh_clicked or detect_clicked or not auto_on:
    render_once()

# Auto-Refresh loop
if auto_on:
    render_once()
    st.caption(f"Auto-refresh is ON — next update in {interval}s")
    time.sleep(interval)
    st.rerun()

# ---------- Manual remediation ----------
st.subheader("Remediation")
action = st.selectbox(
    "Action",
    ["Increase fan target", "Reduce node workload", "Migrate traffic", "Restart service"],
)
params = {}
if action == "Increase fan target":
    params["fan_delta"] = 100
elif action == "Reduce node workload":
    params["workload_factor"] = 0.9

if st.button("Apply Remediation"):
    ok = call_json("POST", f"{API}/remediate", json={"device_id": device, "action": action, "params": params})
    if ok and ok.get("ok"):
        st.success(f"Remediation submitted at {ok.get('ts')}. Effects will appear in new telemetry shortly.")
