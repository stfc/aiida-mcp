# aiida-mcp

An [MCP](https://modelcontextprotocol.io) server for ALC's AiiDA projects. It lets an MCP client (such as an AI assistant) inspect an AiiDA database and submit DL_POLY calculations.

> **Warning:** the server has a write tool (`submit_dlpoly_job`) that is always on. It creates nodes in your AiiDA profile and starts jobs on the daemon. Point it at a profile you are happy to write to.

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Setting up AiiDA](#setting-up-aiida)
- [Running the server](#running-the-server)
- [Connecting a client](#connecting-a-client)
- [Tools](#tools)
- [Submitting a DL_POLY job](#submitting-a-dl_poly-job)
- [Development and tests](#development-and-tests)
- [Troubleshooting](#troubleshooting)

## Requirements

- Python 3.10 or newer. The project is developed and tested on Python 3.14 only.
- `aiida-core` and `mcp`, which are installed as dependencies.
- For DL_POLY jobs: a compiled DL_POLY executable and the optional `aiida-dlpoly` plugin.

You do not need PostgreSQL or RabbitMQ. The setup below uses SQLite and the ZeroMQ broker that AiiDA includes.

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
pip install -e ".[dlpoly]"        # DL_POLY tools (installs aiida-dlpoly)
pip install -e ".[test]"          # pytest, for running the tests
pip install -e ".[dlpoly,test]"   # both
```

Check the install:

```bash
aiida-mcp --help
```

## Setting up AiiDA

The server reads the **default AiiDA profile** from `~/.aiida` (or from the directory in the `AIIDA_PATH` environment variable). If you already have a working profile, skip to [Check the profile](#check-the-profile).

### Create a profile

The quickest option is `verdi presto`. It creates a profile that uses SQLite and needs no other services, makes it the default, and configures `localhost` as a computer:

```bash
verdi presto --profile-name presto
```

If RabbitMQ is running on localhost, `verdi presto` uses it. Otherwise it uses the ZeroMQ broker, which starts with the daemon. For more control, for example PostgreSQL, see `verdi presto --help` and `verdi profile setup`.

### Start the daemon

The daemon runs submitted jobs. Without it, jobs wait in the queue and never run.

```bash
verdi daemon start
```

### Check the profile

```bash
verdi profile list        # the default profile is marked with *
verdi status              # profile, storage, broker and daemon
verdi computer list       # should list localhost
```

To change the default profile, which is the one the server uses:

```bash
verdi profile set-default <name>
```

The server always loads the default profile. If you need it to use another one, change the default before starting the server, or set `AIIDA_PATH` to a different configuration directory.

### Set up a DL_POLY code

Only needed for `submit_dlpoly_job`. Register your DL_POLY executable as a code on the computer it runs on. Use the absolute path to the executable and double-check it exists, because a wrong path only fails when a job runs.

```bash
verdi code create core.code.installed \
    --label dl_poly \
    --computer localhost \
    --filepath-executable /path/to/DLPOLY.Z \
    --default-calc-job-plugin dlpoly \
    --no-with-mpi \
    --non-interactive
```

Notes:

- Drop `--no-with-mpi` and add `--with-mpi` to launch through `mpirun`. In the setup this was developed on, the code ran correctly without `--with-mpi`.
- If your system needs environment modules, add `--prepend-text "module load mpi"` (adjust to your system).
- A stored code's executable path cannot be edited. To fix a wrong path, create a new code, or use `verdi code duplicate`.

Check it:

```bash
verdi code list
verdi code show dl_poly
```

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
|------|--------------|
| `ping` | Checks the server is running. |
| `get_status` | Reports the loaded profile, daemon state and broker connection. |
| `list_processes` | Lists process nodes, newest first. Filters: `state`, `label`, `created_after`, `limit`. |
| `get_process` | Details, inputs and outputs for one process by PK. |
| `get_process_report` | Log messages for one process, oldest first. |
| `list_computers` | Lists configured computers. |
| `list_codes` | Lists codes, optionally for one `computer`. |
| `query_nodes` | Finds nodes by `node_type` prefix, `group` label and `extra_key`. |
| `describe_dlpoly_calcjob` | Describes the DL_POLY calcjob: inputs, outputs, exit codes, default options. |

Notes:

- List tools take a `limit`. The default is 20 (100 for logs), the maximum is 200 (1000 for logs), and a value below 1 is an error.
- `list_processes` states are `created`, `waiting`, `running`, `finished`, `excepted` and `killed`.
- If the daemon is stopped, `get_status` does not check the broker, because connecting would block.
- Errors the caller can fix, such as an unknown state or a missing PK, are returned as short messages.

### Write

| Tool | What it does |
|------|--------------|
| `submit_dlpoly_job` | Builds and submits a DL_POLY calculation to the daemon. |

## Submitting a DL_POLY job

`submit_dlpoly_job` takes:

| Argument | Meaning |
|----------|---------|
| `code` | Label (e.g. `dl_poly@localhost`) or PK of the DL_POLY code. |
| `configuration` | The CONFIG file, or a `StructureData` node. |
| `field` | The FIELD file. |
| `control` | The CONTROL file, or a dict of parameters. |
| `num_machines` | Machines to run on. Default 1. |
| `num_mpiprocs_per_machine` | MPI processes per machine. Default 1. |

Each of `configuration`, `field` and `control` takes **exactly one** of:

- `path`: a file on the machine running the server,
- `text`: the file contents as a string,
- `pk`: an existing node in the database. `configuration` accepts `SinglefileData` or `StructureData`, `field` accepts `SinglefileData`, and `control` accepts `SinglefileData` or `Dict`.

`control` also accepts `parameters`, a dictionary stored as a `Dict` node.

Example arguments:

```json
{
  "code": "dl_poly@localhost",
  "configuration": {"path": "/data/TEST001/CONFIG"},
  "field": {"path": "/data/TEST001/FIELD"},
  "control": {"path": "/data/TEST001/CONTROL"}
}
```

Behaviour:

- The inputs are checked against the calcjob definition before anything is stored. A bad input returns an error and creates no nodes.
- On success the tool returns the process PK and the PKs of the input nodes. Follow the job with `get_process` and `get_process_report`.
- If the daemon is stopped, the job is created and waits until the daemon starts. The result says so.
- Large files are stored in the AiiDA repository. A CONFIG file of about 8 MB is stored in full.
- The server does not wait for the job to finish.

A typical session: call `get_status`, call `list_codes` to find the code, call `submit_dlpoly_job`, then poll `get_process` until `state` is `finished` and check `exit_status`. An `exit_status` of 0 means success. Other values are listed by `describe_dlpoly_calcjob`.

## Development and tests

```bash
pip install -e ".[dlpoly,test]"
pytest
```

The tests create a temporary SQLite profile in a temporary directory, using AiiDA's own pytest fixtures. They do not touch your `~/.aiida` configuration or your profiles. The tests that submit jobs mock the submit call, so no DL_POLY job runs.

Layout:

```
src/aiida_mcp/
  server.py        MCP server, CLI and tool registration
  connection.py    profile loading and status
  processes.py     process tools
  nodes.py         computer, code and node tools
  limits.py        shared limit handling
  plugins/         plugin-specific calcjobs
    __init__.py    list of plugin modules and registration
    calcjob.py     generic describe and submit helpers
    inputs.py      builds input nodes from paths, text, PKs
    dlpoly.py      DL_POLY tools
tests/
```

### Adding a plugin

1. Add a module in `src/aiida_mcp/plugins/` that provides `is_available()` and `register(mcp)`. Use `calcjob.py` for the shared describe and submit logic. `dlpoly.py` is a worked example.
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
