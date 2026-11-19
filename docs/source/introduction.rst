Introduction
============

Welcome to the `aiida-mcp <https://github.com/aiidateam>`_ documentation. ``aiida-mcp`` is a
`Model Context Protocol <https://modelcontextprotocol.io>`_ server for `AiiDA <https://www.aiida.net>`_. It
lets an MCP client, such as an AI assistant, inspect an AiiDA database and submit calculations through a
small, growing set of calcjob plugins (currently DL_POLY, ChemShell and MLIP).

.. warning::

   The server has write tools that are always on: ``submit_dlpoly_job``, ``submit_chemshell_job`` and the
   ``submit_mlip_*_job`` tools create nodes and start jobs on the daemon. Point the server at an AiiDA
   profile you are happy to write to. See :doc:`tools` for the full list of tools and what each one does.

Quick start
-----------

``aiida-mcp`` requires Python 3.10 or newer and depends on ``aiida-core`` and ``mcp``. It should be
installed in the same Python environment as the AiiDA profile it will serve, typically using
`pip <https://pip.pypa.io/en/stable/>`_:

.. code-block:: bash

    git clone <this repository>
    cd aiida-mcp

    python3 -m venv env
    source env/bin/activate

    pip install -e .

Each calcjob plugin is an optional extra, installed only when you need its tools:

.. code-block:: bash

    pip install -e ".[dlpoly]"          # DL_POLY tools (installs aiida-dlpoly)
    pip install -e ".[chemshell]"       # ChemShell tools (installs aiida-chemshell)
    pip install -e ".[mlip]"            # MLIP tools (installs aiida-mlip)
    pip install -e ".[aiidalab]"        # AiiDAlab detection (installs jupyter-server)
    pip install -e ".[test]"            # pytest, for running the tests

A plugin's tools are only registered if its package is installed; without it, the server runs normally
and the plugin's tools are simply absent. Check the install with:

.. code-block:: bash

    aiida-mcp --help

Setting up AiiDA
-----------------

The server reads the **default AiiDA profile** from ``~/.aiida`` (or from the directory given by the
``AIIDA_PATH`` environment variable). If you already have a working profile and daemon, skip ahead to
`Running the server`_.

Create a profile
~~~~~~~~~~~~~~~~~

The quickest option is ``verdi presto``. It creates a profile using SQLite that needs no other services,
makes it the default, and configures ``localhost`` as a computer:

.. code-block:: bash

    verdi presto --profile-name presto

If RabbitMQ is running on localhost, ``verdi presto`` uses it; otherwise it uses the ZeroMQ broker, which
starts with the daemon. For more control, for example PostgreSQL, see ``verdi presto --help`` and
``verdi profile setup``.

Start the daemon
~~~~~~~~~~~~~~~~~

The daemon runs submitted jobs. Without it, jobs wait in the queue and never run:

.. code-block:: bash

    verdi daemon start

Check the profile
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    verdi profile list        # the default profile is marked with *
    verdi status              # profile, storage, broker and daemon
    verdi computer list       # should list localhost

To change the default profile, which is the one the server uses:

.. code-block:: bash

    verdi profile set-default <name>

The server always loads the default profile. If you need it to use another one, change the default
before starting the server, or set ``AIIDA_PATH`` to a different configuration directory. See
:ref:`managing-profiles` for how to create and switch profiles at runtime from an MCP client instead.

Setting up calcjob codes
--------------------------

Each plugin needs an AiiDA code registered for its executable before ``submit_*`` tools for it will work.

DL_POLY
~~~~~~~

Register your DL_POLY executable as a code on the computer it runs on. Use the absolute path to the
executable and double-check it exists, because a wrong path only fails when a job runs:

.. code-block:: bash

    verdi code create core.code.installed \\
        --label dl_poly \\
        --computer localhost \\
        --filepath-executable /path/to/DLPOLY.Z \\
        --default-calc-job-plugin dlpoly \\
        --no-with-mpi \\
        --non-interactive

Drop ``--no-with-mpi`` and add ``--with-mpi`` to launch through ``mpirun``. If your system needs
environment modules, add ``--prepend-text "module load mpi"`` (adjust to your system). A stored code's
executable path cannot be edited; to fix a wrong path, create a new code or use ``verdi code duplicate``.

ChemShell
~~~~~~~~~

Register your ChemShell executable as a code on the computer it runs on:

.. code-block:: bash

    verdi code create core.code.installed \\
        --label chemsh \\
        --computer localhost \\
        --filepath-executable /absolute/path/to/chemsh \\
        --default-calc-job-plugin chemshell \\
        --no-with-mpi \\
        --non-interactive

Whether to pass ``--with-mpi`` depends on which executable you point at, not on whether your ChemShell
build is MPI-enabled: use ``--no-with-mpi`` for the ``chemsh`` wrapper script (it handles launching MPI
itself), and ``--with-mpi`` if you point directly at ``chemsh.x``.

MLIP
~~~~

Register the ``janus`` executable (from ``janus-core``) as a code. The same code can be used for all four
MLIP job types; ``--default-calc-job-plugin`` is just a CLI default suggestion and does not restrict which
entry point the code can be submitted with:

.. code-block:: bash

    verdi code create core.code.installed \\
        --label janus \\
        --computer localhost \\
        --filepath-executable "$(which janus)" \\
        --default-calc-job-plugin mlip.sp \\
        --non-interactive

Check any of these with ``verdi code list`` and ``verdi code show <label>``.

Running the server
--------------------

The server speaks MCP over **stdio** by default, which is what most clients use. The client normally
starts the server itself:

.. code-block:: bash

    aiida-mcp                                   # stdio
    aiida-mcp --transport streamable-http       # HTTP

The HTTP transport listens on ``http://127.0.0.1:8000/mcp``. The host and port are the MCP library's
defaults and the command line does not change them. The HTTP endpoint has no authentication — anything
that can reach it can call every tool, including the write tools, so leave it bound to localhost.

Connecting a client
----------------------

Configure your MCP client to run the ``aiida-mcp`` executable from the virtual environment. Use the
absolute path, since the client usually does not activate the environment:

.. code-block:: text

    /path/to/aiida-mcp/env/bin/aiida-mcp

Many clients use a JSON entry like this one. The file location and exact format differ between clients,
so check your client's documentation:

.. code-block:: json

    {
      "mcpServers": {
        "aiida": {
          "command": "/path/to/aiida-mcp/env/bin/aiida-mcp"
        }
      }
    }

If the server starts but reports no profile, the client may be running it with a different home
directory or environment; add ``AIIDA_PATH`` to the client's environment settings for the server. The
first tool call takes a few seconds, because AiiDA loads its profile and storage on first use.

If your AiiDA profile lives inside an ``aiidalab/full-stack`` Docker container rather than on the local
machine, see :doc:`aiidalab_integration` for running the server inside that container and connecting to
it over ``streamable-http`` instead.

Troubleshooting
------------------

``get_status`` shows ``profile_loaded: false``
    No default profile was found. Run ``verdi profile list``. If the client starts the server, check
    that it sees the same home directory and ``AIIDA_PATH``.

A job stays in the ``waiting`` or ``created`` state
    The daemon is probably not running. Run ``verdi daemon status``, then ``verdi daemon start``.

A newly installed plugin's tools aren't showing up
    The server only checks for installed plugins on startup, because AiiDA and Python both cache entry
    point lookups for the lifetime of the process. Call the ``rescan_plugins`` tool, or restart the
    server, to pick up a plugin package installed afterwards (see :ref:`rescanning-for-plugins`). Make
    sure the package declares an ``aiida_mcp.plugins`` entry point in its own installed metadata.

A job finishes with a non-zero exit status or ``excepted``
    Call ``get_process_report`` with the PK. Compare the exit status with the matching
    ``describe_*_calcjob`` tool, and check that the code's executable path exists
    (``verdi code show <code>``).

The first call is slow
    AiiDA loads the profile and storage on the first call.

A tool call fails with a generic "Error executing tool" message
    Anticipated errors return a clear message; a generic one means something unexpected went wrong. The
    traceback is in the server's stderr, so check your client's MCP logs.
