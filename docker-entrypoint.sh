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

# Start a D-Bus session daemon when one is not already running.
# Required for Gio.Settings (gsettings) signals to work inside the container,
# e.g. `gsettings set org.gnome.desktop.interface color-scheme prefer-dark`.
# --exit-with-session ensures the daemon exits when this process exits.
# Always start a container-local D-Bus session daemon.
# Any DBUS_SESSION_BUS_ADDRESS inherited from the host (e.g. unix:path=/run/user/1000/bus)
# points to a socket that is NOT mounted into the container and fails with
# "No such file or directory".  We unconditionally launch our own daemon and
# override the env var so both the app and any `docker exec` shells use it.

# Create a proper XDG_RUNTIME_DIR owned exclusively by root (mode 0700).
# /tmp (mode 1777) triggers a dbus-daemon warning and causes some portal
# services to refuse to start.
mkdir -p /run/user/0
chmod 700 /run/user/0
export XDG_RUNTIME_DIR=/run/user/0

eval "$(dbus-launch --sh-syntax --exit-with-session)"
export DBUS_SESSION_BUS_ADDRESS

# Write both env vars to a well-known file so `docker exec` shells can pick
# them up with:   source /tmp/dbus-env
printf 'export DBUS_SESSION_BUS_ADDRESS=%s\nexport XDG_RUNTIME_DIR=%s\n' \
    "$DBUS_SESSION_BUS_ADDRESS" "$XDG_RUNTIME_DIR" > /tmp/dbus-env

exec "$@"
