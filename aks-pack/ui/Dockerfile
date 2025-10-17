# aks-pack/ui/Dockerfile
FROM python:3.10-slim

# Install system deps you might need later (optional but safe)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && rm -rf /var/lib/apt/lists/*

# Set the working dir to where the UI code will live
WORKDIR /app/ui

# Install UI requirements
# (Make sure this file exists at repo path: ui/requirements.txt)
COPY ui/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy ONLY the UI app into /app/ui (so dashboard.py is here)
COPY ui/ /app/ui/

# Streamlit defaults
ENV STREAMLIT_SERVER_PORT=8501
EXPOSE 8501

# Run from /app/ui so "dashboard.py" is found without a path prefix
CMD ["python", "-m", "streamlit", "run", "dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
