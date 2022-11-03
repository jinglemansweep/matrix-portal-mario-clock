#!/bin/bash

declare -r script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
declare -r base_dir="${script_dir}/.."
declare -r dest_dir="${1:-/media/${USER}/CIRCUITPY}"

echo "Deploying to Matrix Portal..."
echo
echo "Source Path:    ${base_dir}"
echo "Destination:    ${dest_dir}"
echo

echo "Installing project libraries and dependencies..."
echo
circup install -r "${base_dir}/requirements.txt"
echo

echo "Syncronising project source to destination device (${dest_dir})..."
echo
rsync -r "${base_dir}/src/" "${base_dir}/photos" "${dest_dir}/"
touch "${dest_dir}/code.py" && sync && sleep 1
echo

echo "DONE"
echo