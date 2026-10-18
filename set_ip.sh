#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run this script with sudo or as root."
  exit 1
fi

# Configuration Variables (Change these to match your network)
STATIC_IP="192.168.0.175/24"
GATEWAY="192.168.0.1"
DNS_SERVER="192.168.0.1"
SECONDARY_DNS="8.8.8.8"

# Automatically find the active network interface (excluding loopback)
INTERFACE=$(ip -o link show | awk -F': ' '$2 != "lo" {print $2; exit}')
if [ -z "$INTERFACE" ]; then
  echo "[-] Error: Could not detect an active network interface."
  exit 1
fi
echo "[+] Detected active interface: $INTERFACE"

# Find the existing Netplan YAML file in /etc/netplan/
NETPLAN_FILE=$(ls /etc/netplan/*.yaml | head -n 1)
if [ -z "$NETPLAN_FILE" ]; then
  echo "[-] Error: No Netplan configuration file found in /etc/netplan/"
  exit 1
fi
echo "[+] Found Netplan config: $NETPLAN_FILE"

# Backup the original configuration file
cp "$NETPLAN_FILE" "${NETPLAN_FILE}.bak"
echo "[+] Backup created at ${NETPLAN_FILE}.bak"

# Write the new static IP configuration to the Netplan file
cat << EOF > "$NETPLAN_FILE"
network:
  version: 2
  ethernets:
    $INTERFACE:
      dhcp4: false
      dhcp6: false
      addresses:
        - $STATIC_IP
      routes:
        - to: default
          via: $GATEWAY
      nameservers:
        addresses:
          - $DNS_SERVER
          - $SECONDARY_DNS
EOF

echo "[+] Netplan configuration updated successfully."

netplan apply
