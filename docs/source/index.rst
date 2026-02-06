.. cellpick documentation master file

.. image:: ../../cellpick/assets/logo-h.svg
   :alt: CellPick Logo
   :height: 200
   :width: 4000

CellPick
========

CellPick is a computational tool for facilitating the selection of cells for laser microdissection in single cell proteomics applications.
It introduces a custom shape selection technique that employs a combinatorial optimization procedure for the selection of cells, ensuring the selection of non-contiguous
shapes, while approximately maximizing coverage within a restricted tissue area.

.. image:: _assets/workflow_overview.png
   :alt: CellPick Workflow Overview
   :width: 1000

Key Features
------------

- **Flexible Data Loading**: Load microscopy images (TIFF, CZI) or SpatialData (.zarr) stores with multi-channel support
- **Multi-resolution Support**: Work with large images using adaptive resolution loading
- **Spatial Gradient Analysis**: Establish gradients between landmarks to correlate protein intensities with cell positions
- **Smart Cell Selection**: Multiple algorithms for selecting non-contiguous cells (k-center, random, per-region, per-label)
- **Label-based Selection**: Load cell type labels and select cells stratified by label
- **Per-channel Controls**: Fine-tune visibility and saturation for each channel independently
- **Comprehensive Export**: Export to XML (LMD-compatible) or SpatialData formats


.. grid:: 1 2 2 2
    :gutter: 3

    .. grid-item-card:: Installation
        :link: installation
        :link-type: doc

        Get started with ``cellpick`` installation via pip, pipx, or conda.

    .. grid-item-card:: Launch
        :link: launch
        :link-type: doc

        Learn how to launch the ``cellpick`` application.

    .. grid-item-card:: Workflow
        :link: workflow/index
        :link-type: doc

        Step-by-step guide to the complete ``cellpick`` workflow.

    .. grid-item-card:: Keyboard Shortcuts
        :link: shortcuts
        :link-type: doc

        Reference for all keyboard shortcuts and mouse controls.

    .. grid-item-card:: API Reference
        :link: api
        :link-type: doc

        Detailed documentation of the ``cellpick`` API.

.. toctree::
   :maxdepth: 2
   :hidden:

   installation
   launch
   workflow/index
   shortcuts
   api


