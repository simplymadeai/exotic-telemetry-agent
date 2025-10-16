FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY simulator/ /app/
ENV RCA_API=http://api:8000
CMD ["python", "generator.py"]
