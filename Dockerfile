FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/

EXPOSE 8000
# Observação: em produção (ECS/Lambda) o provider real entra via env LLM_PROVIDER.
ENV LLM_PROVIDER=fixture
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
