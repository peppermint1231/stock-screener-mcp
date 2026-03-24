FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV MCP_TRANSPORT=sse

EXPOSE 8000

CMD ["python", "server/mcp_server.py"]
