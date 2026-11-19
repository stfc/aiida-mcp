#!/bin/bash

# This script is executed whenever the docker container is (re)started.
# Runs after 90_start_aiida_daemon.sh, so the AiiDA profile and daemon are
# already up by the time the MCP server starts in the same environment.
set -x

LOG_FILE="${HOME}/.aiida-mcp.log"

if pgrep -f "aiida-mcp --transport" > /dev/null; then
    echo "aiida-mcp server is already running..."
else
    echo "Starting aiida-mcp server (streamable-http, port 8000)..."
    nohup aiida-mcp --transport streamable-http >> "${LOG_FILE}" 2>&1 &
    disown
fi
