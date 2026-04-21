FROM python:3.11-alpine
RUN apk add --no-cache curl
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8000/ || exit 1
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]