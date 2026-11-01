FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app
COPY main.py .
ENV PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
USER nobody
CMD ["python", "main.py"]
