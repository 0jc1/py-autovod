#!/bin/bash
# shellcheck disable=SC2059

now=$(date +"%T")
g='\033[0;32m'
c='\033[0m'
log_file="autovod_installation.log"

# Log all the outputs of the script to the log file
exec &> >(tee -a "$log_file")

# Check if apt, dnf, or brew is installed
install_command='install'
if command -v apt-get &>/dev/null; then
  package_manager='apt-get'
  update_command='update'
  upgrade_command='upgrade'
  check_install='dpkg -s'
elif command -v dnf &>/dev/null; then
  package_manager='dnf'
  update_command='check-update'
  upgrade_command='upgrade'
  check_install='rpm -q'
elif command -v brew &>/dev/null; then
  package_manager='brew'
  update_command='update'
  upgrade_command='upgrade'
  check_install='brew list -1 | grep -w'
else
  printf "${g}[$now] Error: Could not find a supported package manager. Exiting...${c}\n"
  exit 1
fi

printf "${g}[$now] Updating and upgrading packages...${c}\n"
$package_manager -qq $update_command && $package_manager -qq $upgrade_command

printf "${g}[$now] Installing necessary packages...${c}\n"

# Package names for different package managers
apt_packages=(python3-pip ffmpeg streamlink)
dnf_packages=(python3-pip ffmpeg streamlink)
brew_packages=(python@3.12 ffmpeg streamlink) 

# Use the appropriate package array based on the detected package manager
if [ "$package_manager" = "apt-get" ]; then
  packages=("${apt_packages[@]}")
elif [ "$package_manager" = "dnf" ]; then
  packages=("${dnf_packages[@]}")
elif [ "$package_manager" = "brew" ]; then
  packages=("${brew_packages[@]}")
fi

# Install the packages
for package in "${packages[@]}"; do
  $check_install "$package" &>/dev/null
  if [ $? -eq 0 ]; then
    printf "${g}[$now] $package already installed...${c}\n"
  else
    sudo $package_manager $install_command "$package" -y
  fi
done

# Copy .env.example to .env if .env does not exist
if [ ! -f .env ]; then
  cp .env.example .env
  printf "${g}[$now] Copied .env.example to .env${c}\n"
fi



