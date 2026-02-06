Step 9: Export Results
======================

Once satisfied with your selection, export the results.

Export to XML
-------------

Click **"Export as XML"** to save your selection in LMD-compatible format:

- You'll be prompted for a base filename
- CellPick creates multiple output files:
  - ``<name>.xml``: Shape coordinates in the original format, compatible with LMD systems
  - ``<name>.csv``: Cell IDs with spatial scores (if landmarks were used)
  - ``<name>_landmarks.xml``: Landmark polygons (if landmarks were used)
  - ``<name>_AR.xml``: Active region polygons

.. note::
   If you loaded a downscaled image, CellPick automatically scales coordinates back to full resolution on export.

Export to SpatialData
---------------------

Click **"Export to SpatialData"** to save your selection to a .zarr store:

- Creates a new SpatialData object with:
  - Selected shapes as polygon geometries
  - Associated table with selection metadata
- Compatible with the SpatialData ecosystem for downstream analysis

.. raw:: html

   <div style="margin-bottom: 2em;"></div>

Save Screenshot
---------------

To save a screenshot of the current view:

- Use the menu: **File → Save Screenshot...**
- Or use the keyboard shortcut: **⌘+Shift+S** (Mac) / **Ctrl+Shift+S** (Windows/Linux)
