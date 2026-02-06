Step 2: Adjust Image Display
============================

Once data is loaded, you can fine-tune the image display using the controls in the left panel.

Channel Visibility and Colors
-----------------------------

Each loaded channel appears in the **Channel Control Panel**:

- **Visibility Toggle**: Click the checkbox next to a channel name to show/hide it
- **Rename Channel**: Click on the channel name to rename it
- **Change Color**: Click on the color swatch to open a color picker
- **Remove Channel**: Click the × button to remove a channel

See the channel control panel in the screenshot from Step 1 showing channels with checkboxes for visibility, color swatches, and remove buttons.

.. raw:: html

   <div style="margin-bottom: 2em;"></div>

Per-Channel Saturation Control
------------------------------

CellPick provides fine-grained saturation control for each channel:

- **Auto-adjust Saturation**: When enabled (default), saturation is automatically set based on image percentiles (1st-99th)
- **Manual Saturation**: Disable auto-adjust to reveal per-channel range sliders
  - Each slider has two handles: minimum (left) and maximum (right)
  - Drag handles to adjust the display range for each channel independently
  - The slider color matches the channel color for easy identification

See the saturation sliders below the "Auto-adjust saturation" checkbox in the screenshot from Step 1, showing per-channel range controls.

.. raw:: html

   <div style="margin-bottom: 2em;"></div>

Shape Outline Color
-------------------

- Click **"Select Shape Color"** to choose the outline color for displayed shapes
- This affects how shapes are rendered on top of the image

.. raw:: html

   <div style="margin-bottom: 2em;"></div>

Other View Controls
-------------------

- **Refresh**: Force a redraw of the current view
- **Reset View**: Reset zoom and pan to show the entire image
