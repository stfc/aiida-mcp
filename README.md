# aiida-mcp

An [MCP](https://modelcontextprotocol.io) server for ALC's AiiDA projects. It lets an MCP client (such as an AI assistant) inspect an AiiDA database and submit DL_POLY, ChemShell and MLIP calculations.

> **Warning:** the server has write tools that are always on: `submit_dlpoly_job`, `submit_chemshell_job` and the `submit_mlip_*_job` tools create nodes and start jobs on the daemon, `create_profile` creates new AiiDA profiles and initialises their storage, and `switch_profile` changes the profile every other tool call uses. Point it at a profile you are happy to write to.

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Setting up AiiDA](#setting-up-aiida)
- [Running the server](#running-the-server)
- [Connecting a client](#connecting-a-client)
- [Tools](#tools)
- [Submitting a job](#submitting-a-job)
- [Detecting AiiDAlab](#detecting-aiidalab)
- [Development and tests](#development-and-tests)
- [Troubleshooting](#troubleshooting)

## Requirements

- Python 3.12 or newer. The project is developed and tested on Python 3.14 only.
- `aiida-core` and `mcp`, which are installed as dependencies.
- For DL_POLY jobs: a compiled DL_POLY executable and the optional `aiida-dlpoly` plugin.
- For ChemShell jobs: a compiled ChemShell executable and the optional `aiida-chemshell` plugin.
- For MLIP jobs: the `janus-core` CLI (`janus`) and the optional `aiida-mlip` plugin.
- For AiiDAlab detection: the optional `jupyter-server` dependency (already present if installed alongside AiiDAlab itself).

You do not need PostgreSQL or RabbitMQ to get started — `verdi presto` sets up a profile using SQLite and the ZeroMQ broker that AiiDA includes, with no other services required. See [Setting up AiiDA](#setting-up-aiida).

## Installation

```bash
git clone <this repository>
cd aiida-mcp

python3 -m venv env
source env/bin/activate

pip install -e .
```

Optional extras:

```bash
pip install -e ".[dlpoly]"          # DL_POLY tools (installs aiida-dlpoly)
pip install -e ".[chemshell]"       # ChemShell tools (installs aiida-chemshell)
pip install -e ".[mlip]"            # MLIP tools (installs aiida-mlip)
pip install -e ".[aiidalab]"        # AiiDAlab detection (installs jupyter-server)
pip install -e ".[test]"            # pytest, for running the tests
pip install -e ".[dlpoly,chemshell,mlip,aiidalab,test]"  # all of the above
```

Check the install:

```bash
aiida-mcp --help
```

## Setting up AiiDA

The server needs a working AiiDA profile and daemon to run against, and (for the plugin tools) a code
registered for each executable you want to use. This is standard AiiDA usage, not specific to this
project, so it's covered in full by the [AiiDA documentation](https://aiida.readthedocs.io/projects/aiida-core/en/latest/intro/get_started.html)
(profile and daemon setup) and this project's own [full documentation](https://stfc.github.io/aiida-mcp/)
(profile setup plus registering DL_POLY, ChemShell and MLIP codes specifically).

The one detail specific to this server: it reads the **default AiiDA profile** from `~/.aiida` (or from
the directory in the `AIIDA_PATH` environment variable). Change the default profile with
`verdi profile set-default <name>`, or point `AIIDA_PATH` at a different configuration directory, before
starting the server.

## Running the server

The server speaks MCP over **stdio** by default, which is what most clients use. The client normally starts the server itself.

```bash
aiida-mcp                                   # stdio
aiida-mcp --transport streamable-http       # HTTP
```

The HTTP transport listens on `http://127.0.0.1:8000/mcp`. The host and port are the MCP library's defaults and the command line does not change them. The HTTP endpoint has no authentication. Anything that can reach it can call every tool, including the write tool, so leave it bound to localhost.

## Connecting a client

Configure your MCP client to run the `aiida-mcp` executable from the virtual environment. Use the absolute path, since the client usually does not activate the environment:

```
/path/to/aiida-mcp/env/bin/aiida-mcp
```

Many clients use a JSON entry like this one. The file location and exact format differ between clients, so check your client's documentation:

```json
{
  "mcpServers": {
    "aiida": {
      "command": "/path/to/aiida-mcp/env/bin/aiida-mcp"
    }
  }
}
```

If the server starts but reports no profile, the client may be running it with a different home directory or environment. Add `AIIDA_PATH` to the client's environment settings for the server.

The first tool call takes a few seconds, because AiiDA loads its profile and storage on first use.

## Tools

### Read-only

| Tool | What it does |
| ------ | -------------- |
| `ping` | Checks the server is running. |
| `get_status` | Reports the loaded profile, daemon state and broker connection. |
| `list_processes` | Lists process nodes, newest first. Filters: `state`, `label`, `created_after`, `limit`. |
| `get_process` | Details, inputs and outputs for one process by PK. |
| `get_process_report` | Log messages for one process, oldest first. |
| `list_computers` | Lists configured computers. |
| `list_codes` | Lists codes, optionally for one `computer`. |
| `query_nodes` | Finds nodes by `node_type` prefix, `group` label and `extra_key`. |
| `get_node_content` | Returns the content of a node: file content for `SinglefileData`, the value for `Int`/`Float`, the dictionary for `Dict`, the named arrays for `ArrayData`. |
| `list_profiles` | Lists all configured AiiDA profiles, showing the current and default ones. |
| `get_aiidalab_status` | Reports whether an AiiDAlab server is running locally, and its URL. See [Detecting AiiDAlab](#detecting-aiidalab). |
| `describe_dlpoly_calcjob` | Describes the DL_POLY calcjob: inputs, outputs, exit codes, default options. |
| `describe_chemshell_calcjob` | Describes the ChemShell calcjob: inputs, outputs, exit codes, default options. |
| `describe_mlip_*_calcjob` | Describes the MLIP calcjob: inputs, outputs, exit codes, default options. |

Notes:

- List tools take a `limit`. The default is 20 (100 for logs), the maximum is 200 (1000 for logs), and a value below 1 is an error.
- `list_processes` states are `created`, `waiting`, `running`, `finished`, `excepted` and `killed`.
- If the daemon is stopped, `get_status` does not check the broker, because connecting would block.
- `get_node_content` only supports `SinglefileData`, `Int`, `Float`, `Dict` and `ArrayData` nodes so far; other node types return an error naming the supported ones. File content over 1 MB is truncated, content that cannot be decoded as UTF-8 text is returned base64-encoded, and each array in an `ArrayData` over 1000 rows along its first axis is truncated.
- Errors the caller can fix, such as an unknown state or a missing PK, are returned as short messages.

### Write

| Tool | What it does |
|------|--------------|
| `submit_dlpoly_job` | Builds and submits a DL_POLY calculation to the daemon. |
| `submit_chemshell_job` | Builds and submits a ChemShell calculation to the daemon. |
| `submit_mlip_*_job` | Builds and submits an MLIP calculation to the daemon. |

## Submitting a job

Each supported package has its own submit tool(s), argument reference and worked example in the full
documentation:

- [**DL_POLY**](https://stfc.github.io/aiida-mcp/tools.html#submitting-a-dl-poly-job).
- [**ChemShell**](https://stfc.github.io/aiida-mcp/tools.html#submitting-a-chemshell-job).
- [**MLIP**](https://stfc.github.io/aiida-mcp/tools.html#submitting-an-mlip-job).

All of them share the same behaviour: inputs are validated against the calcjob definition before
anything is stored (a bad input returns an error and creates no nodes), a successful call returns the
process PK and the PKs of the input nodes it created, and a stopped daemon just means the job waits
rather than failing. Follow a submitted job with `get_process` and `get_process_report`, and check
`exit_status` against the codes listed by the matching `describe_*_calcjob` tool.

## Detecting AiiDAlab

`get_aiidalab_status` is meant for the common setup where an AiiDAlab container's startup script launches the MCP server alongside the default Jupyter notebook server, as the same user and in the same Python environment. An MCP client on your local machine can then ask the container "is AiiDAlab up, and what's its URL".

It uses `jupyter_server.serverapp.list_running_servers()`, the same mechanism behind `jupyter server list`, to find Jupyter servers running in that environment. Since it shares the environment with AiiDAlab, this requires no special handling for differing users, home directories, or installed packages.

Requires the `aiidalab` extra (`pip install -e ".[aiidalab]"`), though in the container deployment described above `jupyter-server` is already installed as part of AiiDAlab itself. Without it, the tool reports `running: false` with an explanatory error instead of failing.

Possible results:

- No running server found at all: `{"running": false}`.
- A server whose working directory mentions `aiidalab`, or the sole running server if none do (an AiiDAlab container normally runs only one Jupyter server): `{"running": true, "url": "...", "pid": ..., "root_dir": "...", "version": "..."}`. The URL includes the access token, so it can be opened directly in a browser.
- Several running servers and none clearly AiiDAlab: `{"running": true, "ambiguous": true, "servers": [...]}`, listing every one so the caller can pick the right one (e.g. by `root_dir` or `pid`).

This only detects a server running in the same Python environment as the MCP server. It will not see an AiiDAlab instance running in a different container or on a remote machine.

## Development and tests

```bash
pip install -e ".[dlpoly,chemshell,test]"
pytest
```

The tests create a temporary SQLite profile in a temporary directory, using AiiDA's own pytest fixtures. They do not touch your `~/.aiida` configuration or your profiles. The tests that submit jobs mock the submit call, so no DL_POLY job runs.

CI (`.github/workflows/ci-testing.yml`) runs `ruff check`/`ruff format --check`, then the full test suite with every plugin extra installed (`.[dlpoly,chemshell,mlip,aiidalab,test]`) on Python 3.12 and 3.13; `test_all_tools_are_registered` in `tests/test_server.py` expects that full set of extras. `.github/workflows/ci-docs.yml` builds the Sphinx docs on every push and pull request, and publishes them to GitHub Pages on pushes to `main` (requires enabling Pages with source "GitHub Actions" in the repository settings once).

Layout:

```
src/aiida_mcp/
  server.py        MCP server, CLI and tool registration
  connection.py    profile loading and status
  processes.py     process tools
  nodes.py         computer, code and node tools
  profiles.py      profile listing, creation and switching
  aiidalab.py      AiiDAlab Jupyter server detection
  limits.py        shared limit handling
  plugins/         plugin-specific calcjobs
    __init__.py    list of plugin modules and registration
    calcjob.py     generic describe and submit helpers
    inputs.py      builds input nodes from paths, text, PKs
    dlpoly.py      DL_POLY tools
    chemshell.py   ChemShell tools
    mlip.py        MLIP tools (single point, geometry optimisation, MD, phonons)
tests/
```

### Adding a plugin

1. Add a module in `src/aiida_mcp/plugins/` that provides `is_available()` and `register(mcp)`. Use `calcjob.py` for the shared describe and submit logic, and `calcjob.load_code()` for loading a code by label or PK. `dlpoly.py` is a simple worked example; `chemshell.py` shows a plugin with several optional file and `Dict` inputs; `mlip.py` shows a plugin that registers several calcjobs (one per entry point) from a single module.
2. Add the module's dotted name to `PLUGIN_MODULES` in `plugins/__init__.py`.
3. Add the plugin as an optional dependency in `pyproject.toml`.

A plugin's tools are registered only if its entry point is installed. Without the plugin, the server runs and the tools are absent.

## Troubleshooting

**`get_status` shows `profile_loaded: false`.**
No default profile was found. Run `verdi profile list`. If the client starts the server, check that it sees the same home directory and `AIIDA_PATH`.

**A job stays in the `waiting` or `created` state.**
The daemon is probably not running. Run `verdi daemon status`, then `verdi daemon start`.

**A job finishes with a non-zero exit status or `excepted`.**
Call `get_process_report` with the PK. For DL_POLY, compare the exit status with `describe_dlpoly_calcjob`. Check that the code's executable path exists (`verdi code show <code>`).

**The first call is slow.**
AiiDA loads the profile and storage on the first call.

**A tool call fails with a generic "Error executing tool" message.**
Anticipated errors return a clear message. A generic one means something unexpected went wrong. The traceback is in the server's stderr, so check your client's MCP logs.
