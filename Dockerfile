FROM python:3.8.13-alpine

COPY entrypoint.sh /entrypoint.sh
COPY validate_headers.py /validate_headers.py
COPY supported-licenses.json /supported-licenses.json

ENTRYPOINT ["/entrypoint.sh"]
