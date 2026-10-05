#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 launch.py
status=$?
if [ "$status" -ne 0 ]; then
  printf '\nDayWeave could not start. Install Python 3.12 from python.org and retry.\n'
  printf 'Press Return to close this window.'
  read -r ignored
fi
exit "$status"
