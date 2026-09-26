FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir -e ".[dev]"
COPY . .
RUN sed -i 's/\r$//' docker/entrypoint-api.sh && chmod +x docker/entrypoint-api.sh
EXPOSE 8000
CMD ["docker/entrypoint-api.sh"]
