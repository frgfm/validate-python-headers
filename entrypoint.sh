#!/bin/sh -l
set -eax

python /validate_headers.py "${1}" "${2}" --license "${3}" --folders "${4}" --ignore-files "${5}" --ignore-folders "${6}" --license-notice "${7}"
