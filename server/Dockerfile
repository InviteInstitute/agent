FROM python:3.12-slim

WORKDIR /app
# The learner-model engine first, so a change to the agent alone reuses this layer.
COPY vendor/agent-lm-packages /app/vendor/agent-lm-packages
RUN pip install --no-cache-dir /app/vendor/agent-lm-packages
COPY pyproject.toml /app/
COPY agent /app/agent
COPY migrations /app/migrations
RUN pip install --no-cache-dir /app

RUN useradd --system --uid 10001 agent
USER agent
EXPOSE 8000
# Migrations run before the server starts, so a deploy is one step. nginx on the host is the
# only peer, so its forwarded headers are trusted.
CMD ["sh", "-c", "python -m agent migrate && exec uvicorn agent.app:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*'"]
