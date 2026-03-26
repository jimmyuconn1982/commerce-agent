FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml README.md README.zh-CN.md ./
COPY src ./src
COPY web ./web
COPY db ./db

RUN pip install --no-cache-dir -e .

EXPOSE 10000

CMD ["commerce-agent-web"]
