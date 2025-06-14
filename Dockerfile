FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && apt-get install git -y

ADD . /app

WORKDIR /app

RUN uv sync --locked

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT []

CMD ["gunicorn", "-w", "4", "dbpromotions.server:server", "-b", "0.0.0.0:8022", "--access-logfile", "-"]
