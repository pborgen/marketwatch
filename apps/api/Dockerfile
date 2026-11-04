FROM public.ecr.aws/docker/library/node:22-bookworm-slim AS web

WORKDIR /src
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir "boto3>=1.35"

COPY apps/api/main.py apps/api/auth.py apps/api/agents.py /app/
COPY --from=web /src/dist /app/web

ENV PORT=8000 WEB_DIR=/app/web PYTHONUNBUFFERED=1
EXPOSE 8000
USER nobody
CMD ["python", "main.py"]
