Tools
=====

This page catalogues every tool the server exposes to an MCP client. Tools are plain Python functions
decorated with ``@mcp.tool()`` in :mod:`aiida_mcp.server`; each one's docstring (shown here via
:doc:`the API reference <api/modules>`) is sent to the client verbatim as the tool's description, so it
is worth keeping those docstrings accurate and complete — see :doc:`extending` for the convention.

Read-only tools
----------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Tool
     - What it does
   * - ``ping``
     - Checks the server is running.
   * - ``get_status``
     - Reports the loaded profile, daemon state and broker connection.
   * - ``list_processes``
     - Lists process nodes, newest first. Filters: ``state``, ``label``, ``created_after``, ``limit``.
   * - ``get_process``
     - Details, inputs and outputs for one process by PK.
   * - ``get_process_report``
     - Log messages for one process, oldest first.
   * - ``list_computers``
     - Lists configured computers.
   * - ``list_codes``
     - Lists codes, optionally for one ``computer``.
   * - ``query_nodes``
     - Finds nodes by ``node_type`` prefix, ``group`` label and ``extra_key``.
   * - ``get_node_content``
     - Returns the content of a node: file content for ``SinglefileData``, the value for
       ``Int``/``Float``, the dictionary for ``Dict``, the named arrays for ``ArrayData``.
   * - ``list_profiles``
     - Lists all configured AiiDA profiles, showing the current and default ones.
   * - ``get_aiidalab_status``
     - Reports whether an AiiDAlab server is running locally, and its URL. See `Detecting AiiDAlab`_.
   * - ``describe_dlpoly_calcjob``
     - Describes the DL_POLY calcjob: inputs, outputs, exit codes, default options.
   * - ``describe_chemshell_calcjob``
     - Describes the ChemShell calcjob: inputs, outputs, exit codes, default options.
   * - ``describe_mlip_sp_calcjob``
     - Describes the MLIP single point calcjob.
   * - ``describe_mlip_opt_calcjob``
     - Describes the MLIP geometry optimisation calcjob.
   * - ``describe_mlip_md_calcjob``
     - Describes the MLIP molecular dynamics calcjob.
   * - ``describe_mlip_ph_calcjob``
     - Describes the MLIP phonon calcjob.

Notes:

- List tools take a ``limit``. The default is 20 (100 for logs), the maximum is 200 (1000 for logs), and
  a value below 1 is an error.
- ``list_processes`` states are ``created``, ``waiting``, ``running``, ``finished``, ``excepted`` and
  ``killed``.
- If the daemon is stopped, ``get_status`` does not check the broker, because connecting would block.
- ``get_node_content`` only supports ``SinglefileData``, ``Int``, ``Float``, ``Dict`` and ``ArrayData``
  nodes so far; other node types return an error naming the supported ones. File content over 1 MB is
  truncated, content that cannot be decoded as UTF-8 text is returned base64-encoded, and each array in
  an ``ArrayData`` over 1000 rows along its first axis is truncated.
- Errors the caller can fix, such as an unknown state or a missing PK, are returned as short messages
  (see :func:`aiida_mcp.limits.clamp_limit` and the ``ToolError`` raised throughout
  :mod:`aiida_mcp.nodes` and :mod:`aiida_mcp.processes` for the pattern).

Write tools
------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Tool
     - What it does
   * - ``submit_dlpoly_job``
     - Builds and submits a DL_POLY calculation to the daemon.
   * - ``submit_chemshell_job``
     - Builds and submits a ChemShell calculation to the daemon.
   * - ``submit_mlip_sp_job``
     - Builds and submits an MLIP single point calculation to the daemon.
   * - ``submit_mlip_opt_job``
     - Builds and submits an MLIP geometry optimisation to the daemon.
   * - ``submit_mlip_md_job``
     - Builds and submits an MLIP molecular dynamics run to the daemon.
   * - ``submit_mlip_ph_job``
     - Builds and submits an MLIP phonon calculation to the daemon.
   * - ``create_profile`` *(currently disabled)*
     - Creates a new AiiDA profile and initialises its storage. See `Managing profiles`_.
   * - ``switch_profile`` *(currently disabled)*
     - Switches the server's active AiiDA profile. See `Managing profiles`_.
   * - ``rescan_plugins``
     - Re-checks for installed AiiDA plugins and registers any newly available ones. See
       `Rescanning for plugins`_.

Submitting a DL_POLY job
~~~~~~~~~~~~~~~~~~~~~~~~~

``submit_dlpoly_job`` (:func:`aiida_mcp.plugins.dlpoly.submit_job`) takes:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Argument
     - Meaning
   * - ``code``
     - Label (e.g. ``dl_poly@localhost``) or PK of the DL_POLY code.
   * - ``configuration``
     - The CONFIG file, or a ``StructureData`` node.
   * - ``field``
     - The FIELD file.
   * - ``control``
     - The CONTROL file, or a dict of parameters.
   * - ``num_machines``
     - Machines to run on. Default 1.
   * - ``num_mpiprocs_per_machine``
     - MPI processes per machine. Default 1.
   * - ``label``
     - Optional label to set on the calcjob node.
   * - ``description``
     - Optional description to set on the calcjob node.

Each of ``configuration``, ``field`` and ``control`` takes **exactly one** of ``path`` (a file on the
machine running the server), ``text`` (the file contents as a string), or ``pk`` (an existing node in
the database). ``configuration`` accepts ``SinglefileData`` or ``StructureData``, ``field`` accepts
``SinglefileData``, and ``control`` accepts ``SinglefileData`` or ``Dict``. ``control`` also accepts
``parameters``, a dictionary stored as a ``Dict`` node. This dispatch is implemented by
:func:`aiida_mcp.plugins.inputs.build_node`.

Example arguments:

.. code-block:: json

    {
      "code": "dl_poly@localhost",
      "configuration": {"path": "/data/TEST001/CONFIG"},
      "field": {"path": "/data/TEST001/FIELD"},
      "control": {"path": "/data/TEST001/CONTROL"}
    }

The inputs are checked against the calcjob definition before anything is stored — a bad input returns an
error and creates no nodes. On success the tool returns the process PK and the PKs of the input nodes;
follow the job with ``get_process`` and ``get_process_report``. If the daemon is stopped, the job is
created and waits until the daemon starts, and the result says so. The server does not wait for the job
to finish.

A typical session: call ``get_status``, call ``list_codes`` to find the code, call ``submit_dlpoly_job``,
then poll ``get_process`` until ``state`` is ``finished`` and check ``exit_status``. An ``exit_status`` of
0 means success; other values are listed by ``describe_dlpoly_calcjob``.

Submitting a ChemShell job
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``submit_chemshell_job`` (:func:`aiida_mcp.plugins.chemshell.submit_job`) takes:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Argument
     - Meaning
   * - ``code``
     - Label (e.g. ``chemsh@localhost``) or PK of the ChemShell code.
   * - ``structure``
     - The input structure.
   * - ``structure_index``
     - Index to extract one structure from a multi-structure ``TrajectoryData`` input.
   * - ``structure2``
     - A second input structure, e.g. the final structure for a NEB optimisation.
   * - ``calculation_parameters``
     - Dict of parameters for the ChemShell Task object.
   * - ``optimisation_parameters``
     - Dict of parameters for a geometry optimisation task. Providing this configures an optimisation
       task.
   * - ``qm_parameters``
     - Dict of parameters for the QM Theory object.
   * - ``mm_parameters``
     - Dict of parameters for the MM interface.
   * - ``qmmm_parameters``
     - Dict of parameters for the QM/MM interface.
   * - ``force_field_file``
     - File with force field parameters for the MM interface.
   * - ``output_structure_as_file``
     - If true, return the optimised structure as a ``.cjson`` file instead of a ``StructureData`` node.
       Default false.
   * - ``num_machines``
     - Machines to run on. Default 1.
   * - ``num_mpiprocs_per_machine``
     - MPI processes per machine. Default 4.
   * - ``label``
     - Optional label to set on the calcjob node.
   * - ``description``
     - Optional description to set on the calcjob node.

``structure``, ``structure2`` and ``force_field_file`` each take exactly one of ``path``, ``text`` or
``pk``, as above; ``structure``/``structure2`` accept ``SinglefileData`` (a ``.xyz``, ``.pun`` or
``.cjson`` file), ``StructureData``, or ``TrajectoryData``, and ``force_field_file`` accepts
``SinglefileData``. ``calculation_parameters``, ``optimisation_parameters``, ``qm_parameters``,
``mm_parameters`` and ``qmmm_parameters`` each also take ``parameters``, a dictionary stored as a
``Dict`` node (or ``pk`` of an existing ``Dict`` node).

Example arguments:

.. code-block:: json

    {
      "code": "chemsh@localhost",
      "structure": {"path": "/data/system.xyz"},
      "qm_parameters": {"parameters": {"theory": "nwchem", "basis": "6-31G"}},
      "optimisation_parameters": {"parameters": {}}
    }

Behaviour is the same as ``submit_dlpoly_job``: inputs are validated before anything is stored, the tool
returns the process PK and the PKs of the input nodes it created, and a stopped daemon just means the
job waits. Follow the job with ``get_process`` and ``get_process_report``, and check ``exit_status``
against the codes listed by ``describe_chemshell_calcjob``.

Submitting an MLIP job
~~~~~~~~~~~~~~~~~~~~~~~

There are four MLIP tools — ``submit_mlip_sp_job`` (single point), ``submit_mlip_opt_job`` (geometry
optimisation), ``submit_mlip_md_job`` (molecular dynamics) and ``submit_mlip_ph_job`` (phonons),
implemented by :mod:`aiida_mcp.plugins.mlip` — sharing the same core arguments, plus arguments specific
to each job type.

Shared arguments:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Argument
     - Meaning
   * - ``code``
     - Label (e.g. ``janus@localhost``) or PK of the MLIP code.
   * - ``structure``
     - Path to a structure file on the machine running the server, or the PK of an existing
       ``StructureData`` node.
   * - ``model``
     - Path or URL of the MLIP model file, or the PK of an existing ``ModelData`` node. If omitted, the
       code's own default model for ``architecture`` is used.
   * - ``architecture``
     - MLIP architecture, e.g. ``mace_mp``. Required unless ``model`` is the PK of an existing
       ``ModelData`` node, which already carries its own architecture.
   * - ``device``
     - Device to run on: ``cpu``, ``cuda`` or ``mps``.
   * - ``calc_kwargs``
     - Extra keyword arguments to pass to the selected calculator.
   * - ``num_machines``
     - Machines to run on. Default 1.
   * - ``num_mpiprocs_per_machine``
     - MPI processes per machine. Default 1.
   * - ``label``
     - Optional label to set on the calcjob node.
   * - ``description``
     - Optional description to set on the calcjob node.

Unlike ``configuration``/``field``/``control`` in ``submit_dlpoly_job``, ``structure`` and ``model`` are
plain strings or PKs, not ``{"path": ...}``/``{"pk": ...}`` objects — MLIP's own structure/model loading
helpers (``aiida_mlip.helpers.help_load.load_structure``/``load_model``) are reused directly, and they
already accept either form as a single value.

Job-specific arguments:

- ``submit_mlip_sp_job``: ``out`` (xyz output filename), ``properties`` (list of properties to
  calculate, e.g. ``["energy", "forces"]``).
- ``submit_mlip_opt_job``: ``opt_cell_fully``, ``opt_cell_lengths`` (bools), ``fmax`` (float), ``steps``
  (int), ``minimize_kwargs`` (dict), ``pressure`` (float, GPa).
- ``submit_mlip_md_job``: ``ensemble`` (str, e.g. ``NVT``), ``md_kwargs`` (dict).
- ``submit_mlip_ph_job``: ``out``, ``supercell``, ``qpoint_file`` (str), ``n_qpoints`` (int),
  ``displacement`` (float), ``no_hdf5``, ``dos``, ``pdos``, ``bands``, ``symmetrize`` (bools).

Example arguments for a single point calculation:

.. code-block:: json

    {
      "code": "janus@localhost",
      "structure": "/data/structure.xyz",
      "architecture": "mace_mp",
      "properties": ["energy", "forces"]
    }

Behaviour is the same as ``submit_dlpoly_job``. Follow the job with ``get_process`` and
``get_process_report``, and check ``exit_status`` against the codes listed by the matching
``describe_mlip_*_calcjob`` tool.

.. _rescanning-for-plugins:

Rescanning for plugins
-------------------------

AiiDA caches the list of installed entry points for the lifetime of the Python process
(``aiida.plugins.entry_point.eps``/``eps_select`` are both wrapped in ``functools.cache``). That means
installing a new calcjob plugin package (e.g. ``pip install aiida-dlpoly`` into the server's environment
while it is already running) is invisible to the server until that cache is cleared — restarting the
whole server is one way to do that, but ``rescan_plugins``
(:func:`aiida_mcp.plugins.clear_entry_point_cache` plus :func:`aiida_mcp.plugins.register_all`) does it
without a restart:

1. Clears AiiDA's cached entry point lookups.
2. Re-runs the normal plugin registration pass (:func:`aiida_mcp.plugins.register_all`), which checks
   ``is_available()`` for every module in ``PLUGIN_MODULES`` again and registers tools for any that are
   now available.

Plugins already registered are left alone — registering the same tool name twice is a safe no-op (the
underlying MCP server keeps the existing tool and does not duplicate or error). The response reports both
the full set of currently available plugins and which ones (if any) were newly registered by this call:

.. code-block:: json

    {
      "available": ["aiida_mcp.plugins.dlpoly", "aiida_mcp.plugins.chemshell"],
      "newly_registered": ["aiida_mcp.plugins.chemshell"]
    }

An empty ``newly_registered`` list means nothing changed since the server started (or since the last
successful rescan) — not that the rescan failed.

.. _managing-profiles:

Managing profiles
-------------------

.. note::

   ``create_profile`` and ``switch_profile`` are currently disabled (commented out in
   :mod:`aiida_mcp.server`). ``list_profiles`` is still available.

The server always runs against one loaded profile (see :doc:`introduction`), but it can also create and
switch between profiles at runtime, through :mod:`aiida_mcp.profiles`.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Argument
     - Meaning
   * - ``name``
     - Name for the new profile.
   * - ``email``
     - Default user's email. Required unless ``storage_backend`` is read-only.
   * - ``storage_backend``
     - Storage entry point. Defaults to ``core.sqlite_dos``, which needs no external services.
       ``core.psql_dos`` (PostgreSQL) is also available.
   * - ``storage_config``
     - Backend-specific configuration, e.g. ``{"filepath": "/path/to/dir"}`` for ``core.sqlite_dos``, or
       ``database_username``/``database_password``/``database_name``/``repository_uri`` for
       ``core.psql_dos``. Unset fields fall back to the backend's defaults.
   * - ``broker``
     - Message broker: ``none`` (default), ``core.rabbitmq`` or ``core.zeromq``.
   * - ``first_name``, ``last_name``, ``institution``
     - Optional details for the default user.
   * - ``set_as_default``
     - Makes the new profile the on-disk default, used the next time the server starts.

Example:

.. code-block:: json

    {
      "name": "scratch",
      "email": "me@example.com",
      "storage_config": {"filepath": "/data/aiida-scratch"}
    }

``create_profile`` only creates and initialises the profile; it does not change which profile the
running server uses — call ``switch_profile`` with the profile's ``name`` for that. ``list_profiles``
shows what is configured, which one is the default, and which one the server currently has loaded.

``create_profile`` fails if a profile with that ``name`` already exists, if ``storage_backend`` or
``broker`` is not recognised, or if ``email`` is missing for a non-read-only backend, and nothing is left
behind on failure. ``switch_profile`` fails if ``name`` does not match a configured profile; on success
it loads the profile and initialises its storage, so the next call may take a moment. Switching profiles
affects every subsequent tool call on the server, including from other clients connected to the same
server process.

.. _detecting-aiidalab:

Detecting AiiDAlab
--------------------

``get_aiidalab_status`` (:func:`aiida_mcp.aiidalab.get_status`) is meant for the common setup where an
AiiDAlab container's startup script launches the MCP server alongside the default Jupyter notebook
server, as the same user and in the same Python environment. An MCP client on your local machine can
then ask the container "is AiiDAlab up, and what's its URL". See :doc:`aiidalab_integration` for how to
set that deployment up, including which port to expose for the MCP server itself.

It uses ``jupyter_server.serverapp.list_running_servers()``, the same mechanism behind
``jupyter server list``, to find Jupyter servers running in that environment. Since it shares the
environment with AiiDAlab, this requires no special handling for differing users, home directories, or
installed packages.

Requires the ``aiidalab`` extra (``pip install -e ".[aiidalab]"``), though in the container deployment
described above ``jupyter-server`` is already installed as part of AiiDAlab itself. Without it, the tool
reports ``running: false`` with an explanatory error instead of failing.

Possible results:

- No running server found at all: ``{"running": false}``.
- A server whose working directory mentions ``aiidalab``, or the sole running server if none do (an
  AiiDAlab container normally runs only one Jupyter server): ``{"running": true, "url": "...",
  "pid": ..., "root_dir": "...", "version": "..."}``. The URL includes the access token, so it can be
  opened directly in a browser.
- Several running servers and none clearly AiiDAlab: ``{"running": true, "ambiguous": true,
  "servers": [...]}``, listing every one so the caller can pick the right one (e.g. by ``root_dir`` or
  ``pid``).

This only detects a server running in the same Python environment as the MCP server; it will not see an
AiiDAlab instance running in a different container or on a remote machine.
