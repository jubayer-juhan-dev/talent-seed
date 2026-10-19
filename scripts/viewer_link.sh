#!/bin/sh
# Print the current public link to the Talent Seed viewer (quick-tunnel URL + access key).
# `viewer_link.sh mcp` prints the MCP connector URL for Claude instead.
# The trycloudflare.com URL changes whenever the tunnel service restarts (e.g. after a reboot).
url=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /root/talent-seed/scratch/tunnel.log | tail -1)
key=$(cut -d= -f2- /etc/talent-seed-viewer.env)
[ "$1" = mcp ] && path=/mcp || path=/
echo "${url}${path}?key=${key}"
