FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir "boto3>=1.35"

COPY apps/api/main.py apps/api/auth.py apps/api/agents.py /app/
COPY apps/web/login.html apps/web/monitor.html /app/web/

ENV PORT=8000 WEB_DIR=/app/web PYTHONUNBUFFERED=1
EXPOSE 8000
USER nobody
CMD ["python", "main.py"]
