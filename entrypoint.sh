#!/bin/sh -l
set -eax

python validate_headers.py $1 $2 $3 --folders $4 --ignores $5
