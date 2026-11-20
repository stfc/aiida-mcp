Integrating with AiiDAlab
===========================

`AiiDAlab <https://www.materialscloud.org/aiidalab>`_ is typically run as the
`aiidalab/full-stack <https://github.com/aiidalab/aiidalab-docker-stack>`_ Docker image, which bundles
AiiDA, its daemon, PostgreSQL, RabbitMQ and Jupyter into a single container, exposing only port ``8888``
for the Jupyter notebook. This page describes running ``aiida-mcp`` *inside* that same container, so it
can talk to the AiiDA daemon and plugins already configured there, and reach it from an MCP client outside
the container through a second exposed port.

Why run it inside the container
-----------------------------------

:func:`aiida_mcp.aiidalab.get_status` and the rest of the server assume they can reach a loaded AiiDA
profile directly through the ``aiida-core`` Python API — there is no network protocol between
``aiida-mcp`` and AiiDA itself. The ``aiidalab/full-stack`` image already has a fully configured profile,
daemon, broker and storage running as the ``jovyan`` user in its ``/opt/conda`` environment; the simplest
way to give ``aiida-mcp`` access to all of that is to install and run it **as that same user, in that
same environment, inside the container**, rather than trying to reach into the container from outside.

This matches the deployment :func:`~aiida_mcp.aiidalab.get_status` itself is written for (see
:ref:`managing-profiles` and :ref:`detecting-aiidalab` in :doc:`tools`): it looks for a Jupyter server
in its own Python environment, with no cross-user or cross-container fallback logic, specifically
because the intended setup is "the MCP server and Jupyter are started by the same container, as the
same user."

How the container starts things
-----------------------------------

``aiidalab/full-stack`` is built on the `jupyter/docker-stacks
<https://jupyter-docker-stacks.readthedocs.io/en/latest/using/recipes.html#startup-hooks>`_ convention.
Its entrypoint (``tini -g -- start.sh``) runs, in order:

1. Every script in ``/usr/local/bin/before-notebook.d/`` — in this image, numbered hooks that start
   PostgreSQL, RabbitMQ, prepare the AiiDA profile, and start the AiiDA daemon
   (``90_start_aiida_daemon.sh`` runs ``verdi daemon start``).
2. Every script in ``/usr/local/bin/start-notebook.d/`` — empty by default in this image.
3. The actual Jupyter notebook server (the image's ``CMD``, ``start-notebook.py``).

``.sh`` files in either directory are **sourced**, not executed in a subshell, so anything long-running
must background itself (with ``&``) or it will block the rest of the startup sequence and the notebook
will never start — exactly how the AiiDA daemon itself is started. ``start-notebook.d`` runs after AiiDA's
daemon/broker/storage are already up, which makes it the right place for an ``aiida-mcp`` startup hook.

Exposing a port for the MCP server
---------------------------------------

The server's HTTP transport always binds to ``0.0.0.0:8000`` inside the container (see
:doc:`introduction`); only the ``docker run``/``docker-compose`` port mapping controls what that's
reachable as from outside. Alongside the image's usual ``-p 8888:8888`` for Jupyter, add a mapping for
the MCP port:

.. code-block:: bash

    docker run -d \\
        -p 8888:8888 \\
        -p 8000:8000 \\
        -v aiida-home:/home/jovyan \\
        aiidalab/full-stack-with-mcp:latest

.. warning::

   The HTTP transport has no authentication: anything that can reach port 8000 can call every tool,
   including the write tools that submit jobs. Don't publish it beyond a trusted network — map it to
   ``127.0.0.1:8000:8000`` instead of a public interface unless you put it behind your own
   authenticating proxy or an SSH tunnel.

Installing and starting aiida-mcp in the container
--------------------------------------------------------

Two ways to get ``aiida-mcp`` running inside the container, depending on whether you want something
quick to iterate on or a reproducible image to deploy.

Quick: bind-mount a startup script
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For local development, mount a script into ``start-notebook.d`` and install ``aiida-mcp`` from it at
container startup — no image rebuild needed when the script or the package changes:

.. code-block:: bash

    # start-aiida-mcp.sh
    #!/bin/bash
    pip install --quiet "aiida-mcp[mlip]" "aiida-dlpoly[mcp]" "aiida-chemshell[mcp]"
    aiida-mcp --transport streamable-http > /home/jovyan/aiida-mcp.log 2>&1 &

.. code-block:: bash

    docker run -d \\
        -p 8888:8888 \\
        -p 8000:8000 \\
        -v aiida-home:/home/jovyan \\
        -v "$(pwd)/start-aiida-mcp.sh:/usr/local/bin/start-notebook.d/99-start-aiida-mcp.sh" \\
        aiidalab/full-stack:latest

The script must be executable-looking to ``run-hooks.sh`` by name (it only cares about the ``.sh``
suffix, which it sources) and runs as ``jovyan`` — the same user and ``PATH`` (``/opt/conda/bin/...``)
the AiiDA profile and daemon already use, so ``aiida-mcp`` picks up the pre-configured default profile
with no extra setup.

Production: bake it into a custom image
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For anything beyond local testing, build ``aiida-mcp`` into the image instead of installing it on every
container start:

.. code-block:: dockerfile

    FROM aiidalab/full-stack:latest

    USER root
    # Only needed for plugins with compiled/non-Python dependencies (e.g. DL_POLY, ChemShell, janus-core).
    # RUN apt-get update && apt-get install -y --no-install-recommends <plugin build deps> \\
    #     && rm -rf /var/lib/apt/lists/*

    USER ${NB_USER}
    RUN pip install --no-cache-dir "aiida-mcp[mlip]" "aiida-dlpoly[mcp]" "aiida-chemshell[mcp]"

    COPY --chown=${NB_USER}:${NB_GID} start-aiida-mcp.sh /usr/local/bin/start-notebook.d/99-start-aiida-mcp.sh

where ``start-aiida-mcp.sh`` is the same two-line script as above, minus the ``pip install`` line (since
the package is already in the image):

.. code-block:: bash

    #!/bin/bash
    aiida-mcp --transport streamable-http > /home/jovyan/aiida-mcp.log 2>&1 &

Build and run it the same way, with the same two port mappings:

.. code-block:: bash

    docker build -t aiidalab/full-stack-with-mcp .
    docker run -d -p 8888:8888 -p 8000:8000 -v aiida-home:/home/jovyan aiidalab/full-stack-with-mcp

Connecting a client to the container
------------------------------------------

With the port mapped, point an MCP client at the container's streamable-http endpoint instead of
spawning ``aiida-mcp`` as a local stdio process (contrast with :doc:`introduction`'s local stdio setup):

.. code-block:: json

    {
      "mcpServers": {
        "aiidalab": {
          "url": "http://localhost:8000/mcp"
        }
      }
    }

Replace ``localhost`` with the Docker host's address if the client runs on a different machine — subject
to the same access-control caveat as above. Once connected, ``get_aiidalab_status`` (see
:ref:`detecting-aiidalab` in :doc:`tools`) confirms the client is talking to the right container: it
reports the Jupyter server's own URL and access token, discovered from inside the same environment
``aiida-mcp`` is running in.
