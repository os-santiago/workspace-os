Examples
========

Command-line usage
------------------

.. code-block:: bash

   workspace status
   workspace next
   workspace validate

Python usage
------------

.. code-block:: python

   from pathlib import Path

   from workspace_os.agent_queue import AgentQueueTracker

   tracker = AgentQueueTracker(Path(".workspace-os"))
   report = tracker.utilization_report()
   print(report.render())

Build the docs
--------------

.. code-block:: bash

   sphinx-build -b html docs/api docs/api/_build/html

The generated API pages are refreshed automatically during the Sphinx build.
