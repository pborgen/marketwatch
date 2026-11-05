FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

COPY packages/datafeed /opt/datafeed
COPY packages/envfile /opt/envfile
COPY packages/prompt_management /opt/prompt_management
COPY apps/agents/demo/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir /opt/datafeed /opt/envfile /opt/prompt_management -r /app/requirements.txt

COPY apps/agents/demo/agent.py \
     apps/agents/demo/system_prompt.txt \
     apps/agents/demo/serve.py \
     /app/

# AgentCore calls the container on port 8080. DOCKER_CONTAINER makes the SDK
# listen on 0.0.0.0; locally, `python serve.py` stays on 127.0.0.1.
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DOCKER_CONTAINER=1
EXPOSE 8080
CMD ["python", "serve.py"]
