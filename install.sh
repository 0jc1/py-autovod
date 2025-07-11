#!/bin/bash
# shellcheck disable=SC2059

now=$(date +"%T")
g='\033[0;32m'
c='\033[0m'
log_file="autovod_installation.log"

# Log all the outputs of the script to the log file
exec &> >(tee -a "$log_file")

# Check if apt or dnf is installed
if command -v apt-get &>/dev/null; then
  package_manager='apt-get'
  install_command='install'
  update_command='update'
  upgrade_command='upgrade'
elif command -v dnf &>/dev/null; then
  package_manager='dnf'
  install_command='install'
  update_command='check-update'
  upgrade_command='upgrade'
else
  printf "${g}[$now] Error: Could not find a supported package manager. Exiting...${c}\n"
  exit 1
fi

printf "${g}[$now] Updating and upgrading packages...${c}\n"
$package_manager -qq $update_command && $package_manager -qq $upgrade_command

printf "${g}[$now] Installing necessary Packages...${c}\n"

# Package names for apt
apt_packages=(python3-pip tar ffmpeg streamlink)
# Package names for DNF
dnf_packages=(python3-pip tar ffmpeg streamlink)

# Use the appropriate package array based on the detected package manager
if [ "$package_manager" = "apt-get" ]; then
  packages=("${apt_packages[@]}")
elif [ "$package_manager" = "dnf" ]; then
  packages=("${dnf_packages[@]}")
fi

# Install the packages
for package in "${packages[@]}"; do
  dpkg -s "$package" &>/dev/null
  if [ $? -eq 0 ]; then
    printf "${g}[$now] $package already installed...${c}\n"
  else
    sudo $package_manager $install_command "$package" -y
  fi
done