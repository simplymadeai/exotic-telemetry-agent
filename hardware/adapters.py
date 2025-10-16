import random, datetime
class CanonicalReading:
    def __init__(self, device_id, metrics, provenance):
        self.ts = datetime.datetime.utcnow().isoformat()+"Z"
        self.device_id = device_id
        self.metrics = metrics
        self.provenance = provenance
    def to_event(self):
        evt = {"ts": self.ts, "device_id": self.device_id}
        evt.update(self.metrics); return evt
class BaseAdapter:
    def __init__(self, device_id:str): self.device_id=device_id
    def read(self): raise NotImplementedError
class MockRedfishAdapter(BaseAdapter):
    def read(self):
        import random
        inlet=22.0+random.uniform(-0.5,0.8); fan=4800+random.uniform(-80,80)
        temp=55+max(0,(5000-fan)/50)+(inlet-22)*0.6+random.uniform(0,1.0)
        vcore=1.0+random.uniform(-0.02,0.02); cpu=min(100,30+(temp-55)*0.9+random.uniform(0,3))
        mem=45+random.uniform(0,20); latency=8+(cpu/12)+random.uniform(0,2)
        disk_err=1 if random.random()<0.001 else 0; nic_drop=1 if random.random()<0.0015 else 0
        metrics={"inlet_temp_c":round(inlet,1),"fan_rpm":int(fan),"temp_c":round(temp,1),"vcore_v":round(vcore,3),
                 "cpu_pct":round(cpu,1),"mem_pct":round(mem,1),"disk_errors":disk_err,"nic_drops":nic_drop,"latency_ms":round(latency,1)}
        provenance={"adapter":"redfish","fw_version":"1.2.3","sampling_ms":1000,"notes":"mock"}
        return CanonicalReading(self.device_id, metrics, provenance)
class MockSNMPAdapter(BaseAdapter):
    def read(self):
        import random
        temp=56+random.uniform(-1.0,1.0); fan=5000+random.uniform(-120,120); cpu=35+(temp-55)*0.8+random.uniform(0,2)
        metrics={"inlet_temp_c":22.5,"fan_rpm":int(fan),"temp_c":round(temp,1),"vcore_v":0.98+random.uniform(-0.02,0.02),
                 "cpu_pct":round(cpu,1),"mem_pct":50+random.uniform(-5,5),"disk_errors":0,"nic_drops":0,"latency_ms":8+(cpu/12)+random.uniform(0,2)}
        provenance={"adapter":"snmp","fw_version":"n/a","sampling_ms":1000,"notes":"mock"}
        return CanonicalReading(self.device_id, metrics, provenance)
class MockIPMIAdapter(BaseAdapter):
    def read(self):
        import random
        inlet=23.0+random.uniform(-0.5,0.5); fan=5200+random.uniform(-100,100)
        temp=54+max(0,(5000-fan)/60)+(inlet-23)*0.5+random.uniform(0,1.2); cpu=30+(temp-54)*0.8+random.uniform(0,2)
        metrics={"inlet_temp_c":round(inlet,1),"fan_rpm":int(fan),"temp_c":round(temp,1),"vcore_v":1.01+random.uniform(-0.015,0.015),
                 "cpu_pct":round(cpu,1),"mem_pct":48+random.uniform(-6,6),"disk_errors":0,"nic_drops":0,"latency_ms":8+(cpu/12)+random.uniform(0,2)}
        provenance={"adapter":"ipmi","fw_version":"BMC-4.9.0","sampling_ms":1000,"notes":"mock"}
        return CanonicalReading(self.device_id, metrics, provenance)
class MockModbusAdapter(BaseAdapter):
    def read(self):
        import random
        inlet=21.5+random.uniform(-0.7,0.7); fan=4900+random.uniform(-150,150)
        temp=56+max(0,(5000-fan)/55)+(inlet-21.5)*0.6+random.uniform(0,1.0); cpu=33+(temp-56)*0.85+random.uniform(0,2)
        metrics={"inlet_temp_c":round(inlet,1),"fan_rpm":int(fan),"temp_c":round(temp,1),"vcore_v":1.00+random.uniform(-0.02,0.02),
                 "cpu_pct":round(cpu,1),"mem_pct":47+random.uniform(-4,8),"disk_errors":0,"nic_drops":0,"latency_ms":8+(cpu/12)+random.uniform(0,2)}
        provenance={"adapter":"modbus","fw_version":"mb-0.9","sampling_ms":1000,"notes":"mock"}
        return CanonicalReading(self.device_id, metrics, provenance)
