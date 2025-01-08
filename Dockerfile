FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

RUN pip install poetry

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev

COPY . .

CMD ["python", "main.py"]