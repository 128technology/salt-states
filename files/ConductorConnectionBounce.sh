#!/bin/bash
#
    echo "Now restarting conductor SSH connection 127.0.1.2 ...."
    PIDS=`pgrep -f "/usr/bin/openssh-fips/ssh -L 127.0.1.2" | tr '\n' ' '`
    if [ -z "${PIDS}" ]; then
        echo "no tunnels found for conductor SSH connection 127.0.1.2"
        exit 1
    fi
    kill $PIDS

    sleep 5

    echo "Now restarting conductor SSH connection 127.0.1.3 ...."
    PIDS=`pgrep -f "/usr/bin/openssh-fips/ssh -L 127.0.1.3" | tr '\n' ' '`
    if [ -z "${PIDS}" ]; then
        echo "no tunnels found for conductor SSH connection 127.0.1.3"
        exit 1
    fi
    kill $PIDS
