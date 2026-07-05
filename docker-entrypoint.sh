#!/bin/sh
# Create standard sysfs subdirectories so WebKit's bwrap sandbox can
# bind-mount them.  In this Docker environment /sys has no sysfs mounted
# so none of the expected subdirectories exist.  bwrap requires each
# source path to exist before it can bind it into the sandbox with:
#   bwrap --bind /sys/block       /sys/block \
#         --bind /sys/class/block /sys/class/block \
#         ...
mkdir -p \
    /sys/block \
    /sys/bus \
    /sys/class/block \
    /sys/class/net \
    /sys/dev \
    /sys/devices \
    /sys/firmware \
    /sys/fs \
    /sys/kernel \
    /sys/module \
    /sys/power

exec "$@"
