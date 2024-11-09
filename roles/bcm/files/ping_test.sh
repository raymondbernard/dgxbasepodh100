#!/bin/bash

# File containing the list of IP addresses to ping
ip_file="ip_addresses.txt"

# List of network interfaces to use
interfaces=("10.130.122.254")

# Check if the IP file exists
if [ ! -e "$ip_file" ]; then
  echo "Error: IP address file '$ip_file' not found!"
  exit 1
fi

# Read the IP addresses from the file into an array
ip_addresses=()
while IFS= read -r ip; do
  ip_addresses+=("$ip")
done < "$ip_file"

# Loop through each IP address
for ip in "${ip_addresses[@]}"; do
  # Loop through each network interface
  for iface in "${interfaces[@]}"; do
    # Ping the IP address from the network interface
    ping -c 2 -I "$iface" "$ip"
    echo "Ping result from $iface to $ip: $?"
  done
done
