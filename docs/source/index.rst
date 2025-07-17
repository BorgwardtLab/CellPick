.. cellpick documentation master file, created by
   sphinx-quickstart on Mon Jun 30 16:14:16 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. image:: ../../cellpick/assets/logo-h.svg
   :alt: Load Shapes Dialog
   :height: 200
   :width: 4000

CellPick is a computational tool for facilitating the selection of cells for laser microdissection in single cell proteomics applications.
It introduces a custom shape selection technique that employs a combinatorial optimization procedure for the selection of cells, ensuring the selection of non-contiguous
shapes, while approximately maximizing coverage within a restricted tissue area.

Moreover, as often in spatial proteomics one seeks a statistical correlation between protein intensities and the positions of the cells at hand, this tool makes it easy to establish a gradient along a relevant axis between two landmarks. 
The selected shapes are then automatically endowed with a value indicating how close they are to the two points of interest. This allows to find their position on the gradient of interest, 
which in turn allows to correlate protein intensity levels and the closeness to the landmarks.


.. image:: _assets/workflow_overview.png
   :alt: Load Shapes Dialog
   :width: 1000

.. contents::
   :local:
   :depth: 2

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   launch
   workflow
   api

.. include:: installation.rst
.. include:: launch.rst
.. include:: workflow.rst


