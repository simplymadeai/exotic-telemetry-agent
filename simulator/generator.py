# Legacy simulator (still works if you prefer)
import os, time, json, random, datetime, threading
import requests
API=os.getenv("RCA_API","http://localhost:8000")
DEVICE_IDS=["rack-7-node-1","rack-7-node-2"]
STATE={d:{"fan_delta":0,"workload":1.0} for d in DEVICE_IDS}
def tick(device_id, drift):
    inlet=22.0+random.uniform(-0.5,0.8); base_fan=5000+drift["fan_delta"]
    fan=max(2500, base_fan+random.uniform(-50,50))
    temp=55+max(0,(5000-fan)/45)+(inlet-22)*0.6+random.uniform(0,1.2)
    cpu=min(100,30+(temp-55)*0.9*drift["workload"]+random.uniform(0,3))
    mem=min(100,45+random.uniform(0,20))
    latency=8+(cpu/12)+random.uniform(0,2)
    disk_err=1 if random.random()<0.0015 else 0; nic_drop=1 if random.random()<0.002 else 0
    return {"ts":datetime.datetime.utcnow().isoformat()+"Z","device_id":device_id,"inlet_temp_c":round(inlet,1),
            "cpu_pct":round(cpu,1),"mem_pct":round(mem,1),"temp_c":round(temp,1),"fan_rpm":int(fan),
            "disk_errors":disk_err,"nic_drops":nic_drop,"latency_ms":round(latency,1)}
def inject_faults_loop():
    """Injects hardware faults (fan drop or workload spike) every 5 seconds."""
    import random, time
    while True:
        time.sleep(5)  # ⏱ anomaly every 5 seconds
        target = random.choice(DEVICE_IDS)

        # Simulate a cooling or workload fault
        fault_type = random.choice(["fan_drop", "workload_spike"])
        if fault_type == "fan_drop":
            STATE[target]["fan_delta"] -= random.choice([100, 200, 300])
            print(f"[FAULT] {target}: fan drop injected")
        else:
            STATE[target]["workload"] = min(2.0, STATE[target]["workload"] + 0.2)
            print(f"[FAULT] {target}: workload spike injected")

def poll_actions_loop():
    while True:
        try:
            res=requests.get(f"{API}/actions", timeout=3).json()
            for a in res.get("actions", []):
                dev=a["device_id"]
                if dev in STATE:
                    if a["action"]=="Increase fan target": STATE[dev]["fan_delta"]+=int(a.get("params",{}).get("fan_delta",100))
                    elif a["action"]=="Reduce node workload": STATE[dev]["workload"]=max(0.7, STATE[dev]["workload"]*float(a.get("params",{}).get("workload_factor",0.9)))
                    elif a["action"]=="Migrate traffic": STATE[dev]["workload"]=max(0.8, STATE[dev]["workload"]-0.1)
                    elif a["action"]=="Restart service": STATE[dev]["workload"]=max(0.85, STATE[dev]["workload"]-0.05)
        except Exception: pass
        time.sleep(5)
def emit_loop():
    while True:
        batch=[tick(d, STATE[d]) for d in DEVICE_IDS]
        try: requests.post(f"{API}/ingest", json=batch, timeout=3)
        except Exception: pass
        time.sleep(1)
def main():
    threading.Thread(target=inject_faults_loop, daemon=True).start()
    threading.Thread(target=poll_actions_loop, daemon=True).start()
    emit_loop()
if __name__=="__main__": main()
