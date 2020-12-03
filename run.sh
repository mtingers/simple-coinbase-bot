#!/bin/bash
#
# Wrapper to loop simplebot.py
#

config=$1
if [[ $config == "" ]]; then
    echo "usage: $0 <config-path>"
    exit 1
fi

has_venv=$(python -c 'import os; print(os.environ)' | grep VIRTUAL_ENV)
if [[ $has_venv == "" ]]; then
    echo "ERROR: It looks like you forgot to activate the virtual env. Refusing to run."
    exit 1
fi

while :; do
    python simplebot.py ${config}
    sleep 60
done


