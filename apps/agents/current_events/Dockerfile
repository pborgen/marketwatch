FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

COPY packages/datafeed /opt/datafeed
COPY packages/envfile /opt/envfile
COPY apps/agents/current_events/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir /opt/datafeed /opt/envfile -r /app/requirements.txt

COPY apps/agents/current_events/agent.py \
     apps/agents/current_events/collect.py \
     apps/agents/current_events/documents.py \
     apps/agents/current_events/serve.py \
     apps/agents/current_events/store.py \
     /app/

# AgentCore calls the container on port 8080. DOCKER_CONTAINER makes the SDK
# listen on 0.0.0.0; locally, `python serve.py` stays on 127.0.0.1.
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DOCKER_CONTAINER=1
EXPOSE 8080
CMD ["python", "serve.py"]
