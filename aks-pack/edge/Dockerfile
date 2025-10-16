FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY edge/ hardware/ control/ /app/
ENV RCA_API=http://api:8000
ENV DEVICE_ID=rack-7-node-3
CMD ["python", "edge_agent.py"]
