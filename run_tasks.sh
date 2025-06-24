#!/bin/bash
uv run celery -A dbpromotions.tasks worker -E -B --loglevel=INFO --concurrency=1
