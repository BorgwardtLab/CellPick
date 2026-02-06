Installation
============

We recommend installing CellPick in an isolated environment using `pipx`:

.. code-block:: bash

   pipx install cellpick

.. note::
   You can install pipx using ``pip install pipx``. Running ``pipx ensurepath`` will add pipx (and cellpick) to your PATH.

This will install the ``cellpick`` command globally, isolated from your other Python packages.

Alternative Installation Methods
--------------------------------

Using pip
^^^^^^^^^

You can also install CellPick using pip directly:

.. code-block:: bash

   pip install cellpick

Using conda
^^^^^^^^^^^

For conda users, you can create a dedicated environment:

.. code-block:: bash

   conda create -n cellpick python=3.11
   conda activate cellpick
   pip install cellpick

SpatialData Support
-------------------

To use CellPick with SpatialData (.zarr) files, you need to install the optional SpatialData dependencies:

.. code-block:: bash

   pip install cellpick[spatialdata]

Or install SpatialData separately:

.. code-block:: bash

   pip install spatialdata spatialdata-io

.. note::
   SpatialData support requires Python 3.9 or higher.

