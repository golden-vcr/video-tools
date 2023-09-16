#!/usr/bin/env bash
set -e
HOSTNAME=$(hostname)
OBS_MACHINE_CONFIG_DIR="obs/configs/$HOSTNAME"
if [ -d "$OBS_MACHINE_CONFIG_DIR" ]; then
    echo "ERROR: Machine-specific OBS config already exists at $OBS_MACHINE_CONFIG_DIR!"
    echo "This script will not overwrite existing configuration files."
    echo "Delete this directory manually and try again."
    exit 1
fi

if [ ! -d obs/config/obs-studio ]; then
    echo "ERROR: No OBS config found at obs/config/obs-studio."
    exit 1
fi

echo "This script will copy your OBS config from obs/config/obs-studio to $OBS_MACHINE_CONFIG_DIR."
echo "It will then DELETE obs/config/obs-studio and recreate it as a symlink (i.e. Windows junction) to that directory."
echo "Do you wish to continue? (Only 'yes' will be accepted)."
read -p '> ' CHOICE
if [ "$CHOICE" != "yes" ]; then
    echo "Abort."
    exit 1
fi

echo "Copying config to $OBS_MACHINE_CONFIG_DIR..."
mkdir -p obs/configs
cp -r obs/config/obs-studio "$OBS_MACHINE_CONFIG_DIR"

echo "Deleting obs/config/obs-studio/..."
rm -rf obs/config/obs-studio

echo "Creating a Windows directory junction to activate config..."
MKLINK_CMD="mklink /j obs\\config\\obs-studio obs\\configs\\$HOSTNAME"
cmd //c "$MKLINK_CMD"
echo "Bootstrapped OBS config for $HOSTNAME."

echo "You may now add $OBS_MACHINE_CONFIG_DIR to version control."
