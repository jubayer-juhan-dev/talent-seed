#!/bin/sh
# Print the current public link to the Talent Seed viewer (permanent domain + access key).
# `viewer_link.sh mcp` prints the MCP connector URL for Claude instead.
url=https://talent.jubayerjuhan.site
key=$(grep '^TALENT_SEED_KEY=' /etc/talent-seed-viewer.env | cut -d= -f2-)
[ "$1" = mcp ] && path=/mcp || path=/
echo "${url}${path}?key=${key}"
