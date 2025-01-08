FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app
ENV PORT=8080

RUN pip install poetry gunicorn

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --only main

COPY . .

CMD exec gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT main:app