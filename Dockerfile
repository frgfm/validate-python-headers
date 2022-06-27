FROM python:3.8.13-alpine

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY entrypoint.sh /entrypoint.sh
COPY src/validate_headers.py /validate_headers.py
COPY src/supported-licenses.json /supported-licenses.json

ENTRYPOINT ["/entrypoint.sh"]
