#!/bin/bash

tmpfile=$(mktemp -d) || exit 1
mkdir $tmpfile/lib
find lib -name '*.py' -exec ln {} $tmpfile/{} \;

for script in t128-speedtest-collector t128-speedtest-runner; do
    if [ "$script" = "t128-speedtest-runner" ]; then
        mkdir $tmpfile/plugins
        find plugins -name '*.py' -exec ln {} $tmpfile/{} \;
    fi
    ln $script.py $tmpfile/__main__.py
    python3 -m zipapp --compress --python "/usr/bin/env python3" --output $script.pyz $tmpfile
    rm $tmpfile/__main__.py
done
rm -r $tmpfile
