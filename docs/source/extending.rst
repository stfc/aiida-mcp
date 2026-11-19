Adding support for a new AiiDA plugin
=======================================

``aiida-mcp`` exposes calcjob-specific tools through modules discovered via the ``aiida_mcp.plugins``
entry point group. Any installed package can declare one — it does not need to live in this repo. This
page walks through adding support for a new one, and the shared helpers in :mod:`aiida_mcp.plugins` that
do most of the work for you regardless of where the module lives.

``aiida-mcp`` itself bundles modules for ``aiida-dlpoly``, ``aiida-chemshell`` and ``aiida-mlip`` under
:mod:`aiida_mcp.plugins`, registered through this same entry point mechanism via the entry points declared
in ``aiida-mcp``'s own ``pyproject.toml``. A genuinely third-party AiiDA plugin package would instead
declare its module directly in its *own* ``pyproject.toml`` — see `Registering the module`_ below for both
cases.

The plugin contract
----------------------

A plugin module is any module referenced by an ``aiida_mcp.plugins`` entry point that provides two
functions:

``is_available() -> bool``
    Return whether the underlying AiiDA plugin package is installed, so the server can decide whether to
    register its tools. In practice this is almost always a one-liner delegating to
    :func:`aiida_mcp.plugins.calcjob.calcjob_available`, checking one representative entry point.

``register(mcp: MCPServer) -> None``
    Define and register the plugin's ``@mcp.tool()``-decorated functions on the given server.

:func:`aiida_mcp.plugins.register_all` enumerates every ``aiida_mcp.plugins`` entry point, loads the
module it points at, and calls ``register(mcp)`` only if ``is_available()`` returns ``True``:

.. code-block:: python

    def register_all(mcp: MCPServer) -> list[str]:
        registered = []
        for ep in entry_points(group=ENTRY_POINT_GROUP):
            module = ep.load()
            if module.is_available():
                module.register(mcp)
                registered.append(ep.name)
        return registered

Because ``is_available()`` is checked before anything else, a plugin module must be safe to **import**
even when the AiiDA plugin package it wraps is not installed — never import the third-party package at
module level. :mod:`aiida_mcp.plugins.mlip` demonstrates this: it imports ``aiida_mlip`` only inside the
bodies of the functions that need it, so the module (and the rest of the server) still loads cleanly when
``aiida-mlip`` is absent.

Shared helpers
----------------

Two existing modules do most of the work for you; use them rather than re-implementing their logic.

:mod:`aiida_mcp.plugins.calcjob`
    - :func:`~aiida_mcp.plugins.calcjob.calcjob_available` — check an entry point is installed.
    - :func:`~aiida_mcp.plugins.calcjob.describe_calcjob` — generically describe a calcjob's
      plugin-specific inputs, outputs, exit codes and changed metadata option defaults, straight from its
      ``spec()``. Every ``describe_*_calcjob`` tool in the codebase is a one-line call to this.
    - :func:`~aiida_mcp.plugins.calcjob.submit_calcjob` — validate a dict of inputs against the calcjob
      spec, store any unstored :class:`~aiida.orm.Data` inputs, and submit to the daemon. Nothing is
      stored if validation fails.
    - :func:`~aiida_mcp.plugins.calcjob.load_code` — load a code by label or PK, raising a ``ToolError``
      with a clear message if it does not exist or is ambiguous.

:mod:`aiida_mcp.plugins.inputs`
    - :class:`~aiida_mcp.plugins.inputs.FileInput` — a pydantic model for "give exactly one of ``path``
      (on the machine running the server), ``text``, or ``pk`` (of an existing node)".
      :class:`~aiida_mcp.plugins.inputs.ControlInput` extends it with a ``parameters`` field for building
      a :class:`~aiida.orm.Dict` node inline.
    - :func:`~aiida_mcp.plugins.inputs.build_node` — turn a ``FileInput``/``ControlInput`` into an
      unstored node (from ``path``/``text``/``parameters``) or load an existing one (from ``pk``),
      checking it is one of the accepted types.

Use these for any input that naturally comes from a file, text, or an existing node. If the underlying
AiiDA plugin already ships its own loading helpers with equivalent behaviour (as ``aiida-mlip`` does —
see `When the plugin has its own loaders`_ below), prefer those instead of ``FileInput``/``build_node``,
so you don't duplicate logic the plugin's own maintainers keep in sync with their calcjob.

Worked example: a single calcjob
-----------------------------------

:mod:`aiida_mcp.plugins.dlpoly` is the simplest real example: one calcjob, three file-like inputs, two
resource options. The shape to follow is:

.. code-block:: python

    """<Plugin name> calcjob tools."""

    from typing import Any

    from aiida.engine.daemon.client import get_daemon_client
    from aiida.manage.configuration import get_profile
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError

    from aiida_mcp import connection
    from aiida_mcp.plugins.calcjob import (
        calcjob_available,
        describe_calcjob,
        load_code,
        submit_calcjob,
    )
    from aiida_mcp.plugins.inputs import FileInput, build_node

    ENTRY_POINT = "my_plugin"


    def is_available() -> bool:
        """Return whether the <plugin> calcjob plugin is installed.

        Returns
        -------
        bool
            True if the ``my_plugin`` entry point is installed.
        """
        return calcjob_available(ENTRY_POINT)


    def submit_job(code, some_file: FileInput, num_machines: int = 1, ...) -> dict[str, Any]:
        """Build the inputs for a <plugin> calcjob and submit it to the daemon.

        Parameters
        ----------
        ...

        Returns
        -------
        dict[str, Any]
            The process PK, uuid, label, description, code, input node PKs, and daemon state.
        """
        connection.ensure_profile()

        # validate resources, build the metadata dict (resources/label/description) ...
        inputs = {
            "code": load_code(code),
            "some_file": build_node(some_file, "some_file", "default.txt", (orm.SinglefileData,)),
            "metadata": metadata,
        }

        node = submit_calcjob(ENTRY_POINT, inputs)

        daemon_running = get_daemon_client(get_profile().name).is_daemon_running
        result = {
            "pk": node.pk,
            "uuid": node.uuid,
            "label": node.label,
            "description": node.description,
            "code": inputs["code"].full_label,
            "inputs": {"some_file": inputs["some_file"].pk},
            "daemon_running": daemon_running,
        }
        if not daemon_running:
            result["note"] = "The daemon is not running; the job will wait until it starts."
        return result


    def register(mcp: MCPServer) -> None:
        """Register the <plugin> tools on the given MCP server."""

        @mcp.tool()
        def describe_my_plugin_calcjob() -> dict[str, Any]:
            """Describe the <plugin> calcjob: inputs, outputs, exit codes and defaults."""
            return describe_calcjob(ENTRY_POINT)

        @mcp.tool()
        def submit_my_plugin_job(code, some_file: FileInput, num_machines: int = 1, ...) -> dict[str, Any]:
            """Submit a <plugin> calculation to the daemon; creates nodes and starts a job.

            ... (full numpydoc Parameters/Returns — this docstring is sent to MCP clients verbatim)
            """
            return submit_job(code=code, some_file=some_file, num_machines=num_machines, ...)

Note the split between a plain ``submit_job`` function and the ``@mcp.tool()``-wrapped
``submit_my_plugin_job`` inside ``register()``: the plain function is what tests call directly (so they
don't need a running MCP server or a decorated-function's quirks), and the tool wrapper is a thin,
separately-documented pass-through. Every tool in the codebase follows this split.

Several optional inputs
--------------------------

:mod:`aiida_mcp.plugins.chemshell` shows the next level up: several optional ``FileInput``/
``ControlInput`` and plain scalar inputs. Rather than a long chain of ``if value is not None: inputs[...]
= ...`` statements inline in ``submit_job`` (which quickly trips Ruff's cyclomatic-complexity check,
``C901``), factor that assembly into a small private helper:

.. code-block:: python

    def _optional_inputs(structure_index, structure2, force_field_file, parameters) -> dict[str, Any]:
        inputs: dict[str, Any] = {}
        if structure_index is not None:
            inputs["structure_index"] = orm.Int(structure_index)
        if structure2 is not None:
            inputs["structure2"] = build_node(structure2, "structure2", "structure2.xyz", STRUCTURE_TYPES)
        ...
        for name, value in parameters.items():
            if value is not None:
                inputs[name] = build_node(value, name, f"{name}.json", (orm.Dict,))
        return inputs

``submit_job`` then just does ``inputs.update(_optional_inputs(...))``. The same pattern — a
``_set_scalar(inputs, name, value, wrapper)`` one-liner called repeatedly rather than inlined — is used in
:mod:`aiida_mcp.plugins.mlip` for its many optional boolean/float/int/str inputs.

Several calcjobs from one module
-----------------------------------

Some AiiDA plugins expose more than one calcjob entry point from a shared base class (``aiida-mlip`` has
four: single point, geometry optimisation, MD and phonons). :mod:`aiida_mcp.plugins.mlip` handles this
with one module registering several tools:

- An ``ENTRY_POINTS`` dict mapping short names to entry point strings.
- A ``_common_inputs()`` helper building the inputs every job type shares (code, structure, model,
  device, resources, metadata), called by every ``submit_*_job`` function.
- A ``_submit()`` helper wrapping the shared "call ``submit_calcjob``, build the result dict" logic.
- One ``submit_*_job`` function per entry point, each calling ``_common_inputs()`` then adding its own
  extra inputs.
- ``register()`` registering one ``describe_*_calcjob`` and one ``submit_*_job`` tool per entry point —
  eight tools total, from this one module.

When the plugin has its own loaders
--------------------------------------

Not every input fits ``FileInput``/``build_node`` well. ``aiida-mlip``'s ``structure`` and ``model``
inputs accept a path, a URL (for ``model``), or the PK of an existing node, but as a single string/int
value rather than a ``{"path": ...}``-style object — and ``aiida_mlip.helpers.help_load`` already
provides ``load_structure``/``load_model`` functions implementing exactly that logic (including caching
and deduplicating downloaded models). :mod:`aiida_mcp.plugins.mlip` calls those directly instead of
reinventing them:

.. code-block:: python

    def _load_structure(structure: str | int) -> orm.StructureData:
        from aiida_mlip.helpers.help_load import load_structure

        try:
            return load_structure(structure)
        except Exception as exc:
            raise ToolError(f"structure: {exc}") from exc

The import is kept inside the function (not at module level) for the same reason as ``is_available()``
above: the module must still import cleanly when ``aiida-mlip`` is not installed. When a plugin provides
loaders or validation of its own, prefer wrapping those over duplicating the logic yourself — you get the
same behaviour the plugin's own CLI/workflows use, and it stays correct if the upstream plugin changes
its loading rules.

Registering the module
--------------------------

Once the module exists, declare an ``aiida_mcp.plugins`` entry point pointing at it. Where that
declaration lives depends on whether the module ships in its own package or is bundled in this repo:

**A genuinely third-party AiiDA plugin package** (the expected case — e.g. a new ``aiida-my-plugin``
package with its own ``my_package.mcp`` module) declares the entry point in *its own* ``pyproject.toml``:

.. code-block:: toml

    [project.entry-points."aiida_mcp.plugins"]
    my_plugin = "my_package.mcp"

No change to ``aiida-mcp`` itself is needed — the package just needs to be installed (or reinstalled, so
its entry point metadata is regenerated) alongside ``aiida-mcp``.

**A module bundled in this repo** (as ``dlpoly.py``/``chemshell.py``/``mlip.py`` currently are) instead
needs the entry point declared in *this project's* ``pyproject.toml``:

1. Add its entry point to ``[project.entry-points."aiida_mcp.plugins"]``:

   .. code-block:: toml

       [project.entry-points."aiida_mcp.plugins"]
       dlpoly = "aiida_mcp.plugins.dlpoly"
       chemshell = "aiida_mcp.plugins.chemshell"
       mlip = "aiida_mcp.plugins.mlip"
       my_plugin = "aiida_mcp.plugins.my_plugin"

2. Add the AiiDA plugin package as an optional dependency in ``pyproject.toml``:

   .. code-block:: toml

       [project.optional-dependencies]
       my_plugin = ["aiida-my-plugin"]

3. Reinstall ``aiida-mcp`` (e.g. ``pip install -e .``) so the new entry point is picked up — editable
   installs do not regenerate entry point metadata automatically when ``pyproject.toml`` changes.
4. Update ``test_all_tools_are_registered`` in ``tests/test_server.py`` with the new tool names — but
   only in an environment where the new plugin package is actually installed; see `Testing`_ below.
5. Update :doc:`tools` and the README with the new tools and their arguments.

Docstring convention
------------------------

Project docstrings follow `numpydoc <https://numpydoc.readthedocs.io/en/latest/format.html>`_ style
(enforced for the general shape by Ruff's ``D`` rules with ``convention = "numpy"`` in ``pyproject.toml``,
though Ruff does not check that every parameter is documented under that convention — that's on you).
For any ``@mcp.tool()``-decorated function, the docstring is sent to MCP clients verbatim as the tool's
description (``mcp.server.mcpserver.tools.base`` does ``func_doc = description or fn.__doc__ or ""`` —
there is no structured per-parameter parsing), so a complete ``Parameters``/``Returns``/``Raises``
docstring directly improves what an AI client understands about the tool, not just what a human reading
the source sees.

Testing
----------

Tests for a plugin typically mock the final ``aiida.engine.submit`` call (or, if the AiiDA plugin package
is not installed in the environment running the tests, the ``submit_calcjob`` helper itself — see below)
so that no real job is submitted, then assert on the inputs that *would* have been submitted:

.. code-block:: python

    @pytest.fixture
    def fake_submit():
        node = orm.CalcJobNode()
        node.set_process_type("aiida.calculations:my_plugin")
        with mock.patch.object(calcjob, "submit", return_value=node) as patched:
            node.store_all = lambda: None
            yield patched

If the real AiiDA plugin package is installed in the test environment (as ``aiida-dlpoly`` and
``aiida-chemshell`` are in this project's own development environment), mocking only the final
``aiida.engine.submit`` call still exercises the real calcjob's input validation — so tests can assert on
genuine ``ToolError`` messages raised by the plugin's own ``validate_inputs``, not just this project's
glue code.

If the real package is **not** installed (as was the case developing :mod:`aiida_mcp.plugins.mlip`), the
real entry point is not registered with AiiDA at all, so ``calcjob.CalculationFactory(entry_point)`` —
called inside :func:`~aiida_mcp.plugins.calcjob.submit_calcjob` before the mocked ``submit`` is ever
reached — fails. In that situation, mock the plugin module's own ``submit_calcjob`` name instead (bypassing
real spec validation entirely), and, if the plugin module imports helper functions from the third-party
package lazily (as described in `When the plugin has its own loaders`_), inject minimal fake modules via
``sys.modules`` that mimic the handful of functions/classes actually used:

.. code-block:: python

    @pytest.fixture
    def fake_aiida_mlip(monkeypatch):
        help_load = types.ModuleType("aiida_mlip.helpers.help_load")
        help_load.load_structure = lambda value: orm.StructureData()
        help_load.load_model = lambda value, architecture, cache_dir=None: orm.SinglefileData(...)
        modules = {
            "aiida_mlip": types.ModuleType("aiida_mlip"),
            "aiida_mlip.helpers": types.ModuleType("aiida_mlip.helpers"),
            "aiida_mlip.helpers.help_load": help_load,
            ...
        }
        for name, module in modules.items():
            monkeypatch.setitem(sys.modules, name, module)

Tests built this way verify the plugin module's own glue logic (input assembly, error handling, resource
validation) correctly, but **not** the real third-party package's actual behaviour — treat them as a
stopgap, and prefer installing the real package in the test environment once that's possible, matching
how ``aiida-dlpoly`` and ``aiida-chemshell`` are tested in this project today.
