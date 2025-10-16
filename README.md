# 🌌 Exotic Telemetry Agent (v1.2 — Hardware Edition)
**New:** Edge agent with hardware adapters (Redfish/SNMP/IPMI/Modbus mocks), canonical schema with units, PID control demo, optional MQTT.
## Run
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python api/app.py
python edge/edge_agent.py
streamlit run ui/dashboard.py
