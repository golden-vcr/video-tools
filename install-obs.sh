#!/usr/bin/env bash
set -e
OBS_VERSION="29.1.3"
OBS_ZIP_FILENAME="OBS-Studio-$OBS_VERSION.zip"
OBS_ZIP_URL="https://github.com/obsproject/obs-studio/releases/download/$OBS_VERSION/$OBS_ZIP_FILENAME"

if [ "$1" == "uninstall" ]; then
    if [ ! -d obs/bin ]; then
        echo "OBS is not installed."
    else
        if [ -d obs/config/obs-studio ]; then
            echo "WARNING: OBS configuration data in obs/config/obs-studio will be deleted."
            echo "Continue with uninstall? (Only 'yes' will be accepted)."
            read -p '> ' CHOICE
            if [ "$CHOICE" != "yes" ]; then
                echo "Abort."
                exit 1
            fi
        fi
        echo "Uninstalling the portable copy of OBS from obs/..."
        rm -rf obs/bin
        rm -rf obs/config
        rm -rf obs/data
        rm -rf obs/obs-plugins
        echo "The portable copy of OBS has been uninstalled."
        echo "Re-run this script without arguments to install a fresh copy of OBS v$OBS_VERSION."
    fi
    exit 0
fi

if [ ! -d obs/bin ]; then
    echo "Installing a portable copy of OBS v$OBS_VERSION to obs/..."
    rm -f $OBS_ZIP_FILENAME
    curl -L $OBS_ZIP_URL -o $OBS_ZIP_FILENAME
    unzip $OBS_ZIP_FILENAME -d obs
    rm $OBS_ZIP_FILENAME
fi
echo "OBS is installed locally at obs/."

HOSTNAME=$(hostname)
OBS_MACHINE_CONFIG_DIR="obs/configs/$HOSTNAME"
if [ -d "$OBS_MACHINE_CONFIG_DIR" ]; then
    echo "Machine-specific OBS config found at $OBS_MACHINE_CONFIG_DIR."
    if [ ! -d obs/config/obs-studio ]; then
        echo "Creating a Windows directory junction to activate config..."
        mkdir -p obs/config
        MKLINK_CMD="mklink /j obs\\config\\obs-studio obs\\configs\\$HOSTNAME"
        cmd //c "$MKLINK_CMD"
        echo "Activated OBS config for $HOSTNAME."
    else
        echo "However, obs/config/obs-studio already exists."
        echo "Existing OBS configuration will not be modified."
    fi
else
    echo "No machine-specific OBS config found at $OBS_MACHINE_CONFIG_DIR."
    echo "OBS must be configured manually."
fi
