FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# service mode: join every new room whose name starts with "call-".
# Railway injects env vars, so the missing ../.env is fine.
CMD ["python", "agent.py", "--watch", "call-"]
