import os, time, requests, threading
from hardware.adapters import MockRedfishAdapter  # or MockSNMPAdapter, MockIPMIAdapter, MockModbusAdapter
from control.pid import PID
API=os.getenv("RCA_API","http://localhost:8000")
DEVICE_ID=os.getenv("DEVICE_ID","rack-7-node-3")
SAMPLE_PERIOD=float(os.getenv("SAMPLE_PERIOD","1.0"))
adapter=MockRedfishAdapter(device_id=DEVICE_ID)
pid=PID(setpoint=55.0)
fan_target_delta=0.0
def post_events(batch):
    try: requests.post(f"{API}/ingest", json=batch, timeout=5)
    except Exception: pass
def actions_poller():
    global fan_target_delta
    while True:
        try:
            r=requests.get(f"{API}/actions", timeout=5).json()
            for a in r.get("actions", []):
                if a.get("device_id")!=DEVICE_ID: continue
                act=a.get("action"); params=a.get("params",{})
                if act=="Increase fan target": fan_target_delta+=int(params.get("fan_delta",100))
                elif act=="Reduce node workload": fan_target_delta-=20
                elif act=="Migrate traffic": fan_target_delta-=50
                elif act=="Restart service": fan_target_delta-=30
        except Exception: pass
        time.sleep(5)
def main():
    threading.Thread(target=actions_poller, daemon=True).start()
    while True:
        reading=adapter.read()
        temp=reading.metrics.get("temp_c",55.0)
        correction=pid.update(temp, dt=SAMPLE_PERIOD)
        reading.metrics["fan_rpm"]=max(2500, int(reading.metrics["fan_rpm"] + fan_target_delta + correction))
        post_events([reading.to_event()])
        time.sleep(SAMPLE_PERIOD)
if __name__=="__main__": main()
