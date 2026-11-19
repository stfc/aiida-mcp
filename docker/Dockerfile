FROM aiidalab/full-stack:latest

LABEL maintainer="Dr. Benjamin T. Speake <benjamin.speake@stfc.ac.uk>"
LABEL org.opencontainers.image.source="https://github.com/stfc/aiida-mcp"

# Git ref (branch, tag or commit) of stfc/aiida-mcp to install, and the
# optional extras to pull in alongside it (comma-separated, no spaces).
ARG AIIDA_MCP_REF=main
ARG AIIDA_MCP_EXTRAS=aiidalab

# aiida-core and jupyter-server are already provided by the base image, so
# this just adds the MCP server itself. Runs as the default jovyan user,
# which is how AiiDAlab images install everything else too.
RUN pip install --no-cache-dir \
    "aiida-mcp[${AIIDA_MCP_EXTRAS}] @ git+https://github.com/stfc/aiida-mcp.git@${AIIDA_MCP_REF}"

COPY 91_start_aiida_mcp.sh /usr/local/bin/before-notebook.d/

# Matches the port aiida_mcp.server.main() binds for the streamable-http
# transport.
EXPOSE 8000
