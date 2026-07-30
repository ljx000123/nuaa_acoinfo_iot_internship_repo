#!/bin/sh

echo "Waiting for system time synchronization..."

while true
do
    SYNC=$(timedatectl show -p NTPSynchronized --value)

    if [ "$SYNC" = "yes" ]; then
        echo "Time synchronized."
        break
    fi

    sleep 5
done
