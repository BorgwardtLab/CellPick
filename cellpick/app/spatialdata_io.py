"""
SpatialData integration module for CellPick.

This module provides functionality to load and export spatial omics data
in SpatialData format (.zarr stores).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import warnings

import numpy as np
import pandas as pd
from PySide6.QtCore import QPointF
from shapely.geometry import Polygon as ShapelyPolygon
from scipy.ndimage import find_objects

try:
    import spatialdata as sd
    from spatialdata.models import Image2DModel, ShapesModel, TableModel
    from spatialdata.transformations import Identity
    import xarray as xr
    from skimage import measure
    import geopandas as gpd

    # Silence zarr warnings about .DS_Store and other non-zarr files
    warnings.filterwarnings(
        "ignore", message=".*not recognized as a component of a Zarr hierarchy.*"
    )

    SPATIALDATA_AVAILABLE = True
except ImportError:
    SPATIALDATA_AVAILABLE = False


class SpatialDataLoader:
    """
    Loader for SpatialData .zarr stores.

    Attributes
    ----------
    sdata : SpatialData
        The loaded SpatialData object.
    path : Path
        Path to the .zarr store.
    """

    def __init__(self, path: str) -> None:
        """
        Initialize the SpatialData loader.

        Parameters
        ----------
        path : str
            Path to the .zarr store.

        Raises
        ------
        ImportError
            If spatialdata is not installed.
        FileNotFoundError
            If the .zarr store does not exist.
        """
        if not SPATIALDATA_AVAILABLE:
            raise ImportError(
                "SpatialData is not installed. "
                "Please install it with: pip install spatialdata spatialdata-io spatialdata-plot"
            )

        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"SpatialData store not found: {path}")

        self.sdata = sd.read_zarr(path)

    def get_available_images(self) -> List[str]:
        """
        Get list of available image elements.

        Returns
        -------
        List[str]
            Names of available images.
        """
        if hasattr(self.sdata, "images"):
            return list(self.sdata.images.keys())
        return []

    def get_available_labels(self) -> List[str]:
        """
        Get list of available label (segmentation) elements.

        Returns
        -------
        List[str]
            Names of available labels.
        """
        if hasattr(self.sdata, "labels"):
            return list(self.sdata.labels.keys())
        return []

    def get_available_shapes(self) -> List[str]:
        """
        Get list of available shape elements.

        Returns
        -------
        List[str]
            Names of available shapes.
        """
        if hasattr(self.sdata, "shapes"):
            return list(self.sdata.shapes.keys())
        return []

    def get_available_tables(self) -> List[str]:
        """
        Get list of available table elements.

        Returns
        -------
        List[str]
            Names of available tables.
        """
        if hasattr(self.sdata, "tables"):
            return list(self.sdata.tables.keys())
        return []

    def get_categorical_columns(self, table_name: Optional[str] = None) -> List[str]:
        """
        Get categorical columns from a table in the SpatialData object.

        Parameters
        ----------
        table_name : Optional[str]
            Name of the table to get columns from. If None, uses the first available table.

        Returns
        -------
        List[str]
            List of categorical column names from the table.
        """
        tables = self.get_available_tables()
        if not tables:
            return []

        if table_name is None:
            table_name = tables[0]

        if table_name not in tables:
            return []

        table = self.sdata.tables[table_name]
        categorical_cols = []

        # Check obs (observations/cells metadata) for categorical columns
        if hasattr(table, "obs"):
            for col in table.obs.columns:
                if col.startswith("_"):
                    continue

                # Check if column is categorical
                col_data = table.obs[col]

                # Pandas categorical dtype
                if pd.api.types.is_categorical_dtype(col_data):
                    categorical_cols.append(col)
                # String/object dtype with limited unique values (likely categorical)
                elif pd.api.types.is_object_dtype(
                    col_data
                ) or pd.api.types.is_string_dtype(col_data):
                    n_unique = col_data.nunique()
                    n_total = len(col_data)
                    # If less than 20% unique values and less than 100 unique values, treat as categorical
                    if n_unique < min(100, n_total * 0.2) and n_unique > 1:
                        categorical_cols.append(col)

        return categorical_cols

    def get_cell_labels(
        self,
        label_column: str,
        table_name: Optional[str] = None,
        instance_column: Optional[str] = None,
    ) -> Optional[Dict[int, Any]]:
        """
        Get labels for each cell from a table column.

        Parameters
        ----------
        label_column : str
            Name of the column containing labels.
        table_name : Optional[str]
            Name of the table to get labels from. If None, uses the first available table.

        Returns
        -------
        Optional[Dict[int, Any]]
            Dictionary mapping cell indices (0-based) to their labels, or None if not found.
            The indices correspond to the order of cells as loaded into CellPick.
        """
        tables = self.get_available_tables()
        if not tables:
            return None

        if table_name is None:
            table_name = tables[0]

        if table_name not in tables:
            return None

        table = self.sdata.tables[table_name]

        # Check in obs (observations/cells metadata)
        if hasattr(table, "obs") and label_column in table.obs.columns:
            labels_dict = {}

            # Determine which column contains instance IDs. Preference order:
            # 1) caller-provided instance_column
            # 2) spatialdata_attrs.instance_key
            # 3) any obs column containing 'cell_id' or ending with '_id'
            # 4) fallback to row index
            instance_key = None
            if instance_column and instance_column in table.obs.columns:
                instance_key = instance_column

            if (
                instance_key is None
                and hasattr(table, "uns")
                and "spatialdata_attrs" in table.uns
            ):
                attrs = table.uns["spatialdata_attrs"]
                if "instance_key" in attrs:
                    cand = attrs["instance_key"]
                    if cand in table.obs.columns:
                        instance_key = cand

            if instance_key is None:
                for c in table.obs.columns:
                    if "cell_id" in c.lower() or c.lower().endswith("_id"):
                        instance_key = c
                        break

            if instance_key is None:
                instance_key = "index"

            # Gather instance values and labels
            if instance_key == "index":
                instances = table.obs.index.tolist()
            else:
                instances = (
                    table.obs[instance_key].tolist()
                    if instance_key in table.obs.columns
                    else table.obs.index.tolist()
                )

            label_values = table.obs[label_column].tolist()

            # Helper to coerce values to int when possible
            def _coerce_int(v):
                try:
                    if isinstance(v, (int, np.integer)):
                        return int(v)
                    if isinstance(v, float) and v.is_integer():
                        return int(v)
                    if isinstance(v, str) and v.strip().isdigit():
                        return int(v.strip())
                except Exception:
                    pass
                return None

            coerced = [_coerce_int(x) for x in instances]
            numeric_ids = [c for c in coerced if c is not None]

            # Map instance IDs directly to labels WITHOUT modification
            # The original_id in Polygon objects should match these raw instance IDs
            for idx, (inst, lbl) in enumerate(zip(instances, label_values)):
                # Normalize label values
                try:
                    if pd.isna(lbl):
                        lbl = ""
                    elif isinstance(lbl, str):
                        lbl = lbl.strip()
                except Exception:
                    pass

                cid = _coerce_int(inst)
                if cid is not None:
                    # Use the ORIGINAL instance ID as the key (no 0/1-based conversion)
                    # This must match Polygon.original_id which comes from the segmentation mask
                    labels_dict[int(cid)] = lbl
                else:
                    # Non-numeric ID: use row index as fallback
                    labels_dict[idx] = lbl

            return labels_dict

        return None

    def extract_image_channels(
        self, image_name: Optional[str] = None, scale_level: int = 0
    ) -> Tuple[List[np.ndarray], List[str]]:
        """
        Extract image channels from a SpatialData image element.

        Parameters
        ----------
        image_name : Optional[str]
            Name of the image element. If None, uses the first available.
        scale_level : int
            Which scale level to extract (0 = highest resolution).

        Returns
        -------
        Tuple[List[np.ndarray], List[str]]
            List of channel arrays and their names.
        """
        if not self.get_available_images():
            return [], []

        if image_name is None:
            image_name = self.get_available_images()[0]

        image = self.sdata.images[image_name]

        # Get the appropriate scale level
        if hasattr(image, "__iter__") and not isinstance(image, xr.DataArray):
            # Multi-scale image (DataTree)
            image_data = sd.get_pyramid_levels(image, n=scale_level)
        else:
            # Single-scale image
            image_data = image

        # Prefer working with xarray DataArray when possible to avoid ambiguous
        # indexer issues (coords with None/object dtype). Use .isel for integer
        # indexing and fall back to numpy-safe operations.
        channels = []
        channel_names = []

        try:
            is_xarray = isinstance(image_data, xr.DataArray)
        except Exception:
            is_xarray = False

        if is_xarray:
            # If 'c' is a dimension, iterate safely with isel
            dims = list(image_data.dims)
            if "c" in dims:
                n_channels = int(image_data.sizes.get("c", 0))

                # Get channel names robustly
                try:
                    coord_vals = image_data.coords.get("c", None)
                    if coord_vals is not None:
                        channel_coords = list(coord_vals.values)
                        channel_names = [str(c) for c in channel_coords]
                    else:
                        channel_names = [f"Channel_{i}" for i in range(n_channels)]
                except Exception:
                    channel_names = [f"Channel_{i}" for i in range(n_channels)]

                for i in range(n_channels):
                    try:
                        ch_da = image_data.isel({"c": i})
                        ch_arr = (
                            ch_da.compute().values
                            if hasattr(ch_da, "compute")
                            else ch_da.values
                        )
                        ch_arr = np.squeeze(np.asarray(ch_arr))
                        if ch_arr.ndim == 2:
                            channels.append(ch_arr)
                    except Exception:
                        # Skip problematic channel
                        continue
            else:
                # No channel dimension: treat as single 2D image
                arr = (
                    image_data.compute().values
                    if hasattr(image_data, "compute")
                    else image_data.values
                )
                arr = np.squeeze(np.asarray(arr))
                if arr.ndim == 2:
                    channels.append(arr)
                    channel_names.append(image_name)
        else:
            # Fallback: treat image_data as numpy-like
            image_array = (
                image_data.compute()
                if hasattr(image_data, "compute")
                else getattr(image_data, "values", image_data)
            )
            image_array = np.asarray(image_array)

            # Derive axes via spatialdata helper if available, else assume (c,y,x) or (y,x,c)
            try:
                axes = sd.models.get_axes_names(image_data)
            except Exception:
                axes = []

            if "c" in axes:
                c_idx = axes.index("c")
                n_channels = int(image_array.shape[c_idx])
                channel_names = [f"Channel_{i}" for i in range(n_channels)]

                for i in range(n_channels):
                    # index safely using integer positions
                    slc = [slice(None)] * image_array.ndim
                    slc[c_idx] = i
                    channel_data = np.squeeze(image_array[tuple(slc)])
                    if channel_data.ndim == 2:
                        channels.append(channel_data)
            else:
                channel_data = np.squeeze(image_array)
                if channel_data.ndim == 2:
                    channels.append(channel_data)
                    channel_names.append(image_name)

        return channels, channel_names

    def extract_polygons_from_labels(
        self,
        label_name: Optional[str] = None,
        min_area: int = 10,
        max_cells: int = 10000,
        progress_callback: Optional[callable] = None,
    ) -> List[Tuple[List[QPointF], str, int]]:
        """
        Extract polygons from segmentation labels.

        Parameters
        ----------
        label_name : Optional[str]
            Name of the label element. If None, uses the first available.
        min_area : int
            Minimum area (in pixels) for a polygon to be included.
        max_cells : int
            Maximum number of cells to extract (to prevent hanging on huge datasets).
        progress_callback : Optional[callable]
            Callback function(current, total) to report progress.

        Returns
        -------
        List[Tuple[List[QPointF], str, int]]
            List of (polygon_points, label, original_mask_id) tuples.
        """
        if not self.get_available_labels():
            return []

        if label_name is None:
            # Prefer cytosol/cell masks over nuclear masks
            available = self.get_available_labels()
            label_name = None

            # Look for cytosol or cell masks first
            for name in available:
                if (
                    "cyt" in name.lower() or "cell" in name.lower()
                ) and "cellpick" not in name.lower():
                    label_name = name
                    break

            # If no cytosol/cell mask found, use first available
            if label_name is None:
                label_name = available[0]

            print(f"Using label mask: '{label_name}' (available: {available})")

        labels = self.sdata.labels[label_name]

        # Get the appropriate scale level (highest resolution)
        if hasattr(labels, "__iter__") and not isinstance(labels, xr.DataArray):
            label_data = sd.get_pyramid_levels(labels, n=0)
        else:
            label_data = labels

        # Convert to numpy
        label_array = (
            label_data.compute()
            if hasattr(label_data, "compute")
            else label_data.values
        )
        label_array = np.squeeze(np.asarray(label_array))

        polygons = []

        # Convert to integer array for find_objects
        try:
            label_array_int = label_array.astype(np.int32)
        except Exception:
            # Fallback: convert to numeric first
            flat = label_array.ravel()
            numeric = pd.to_numeric(flat, errors="coerce")
            label_array_int = numeric.values.reshape(label_array.shape)
            label_array_int = np.nan_to_num(label_array_int, 0).astype(np.int32)

        # FAST: Pre-compute bounding boxes for ALL labels at once
        # slices[i] contains the bounding box for label (i+1)
        slices = find_objects(label_array_int)

        if not slices:
            return []

        # Get valid label IDs that have bounding boxes
        valid_labels = [i + 1 for i, s in enumerate(slices) if s is not None]

        # Limit number of cells
        total_cells = len(valid_labels)
        if total_cells > max_cells:
            print(f"Warning: Found {total_cells} cells, limiting to {max_cells}")
            valid_labels = valid_labels[:max_cells]

        # Get image dimensions
        img_height, img_width = label_array_int.shape
        padding = 25  # Pixel padding around bounding box

        # Iterate over valid label ids
        for idx, label_id in enumerate(valid_labels):
            # Report progress
            if progress_callback and idx % 100 == 0:
                progress_callback(idx, len(valid_labels))

            # 1) Get pre-computed bounding box (instant lookup!)
            bbox = slices[label_id - 1]  # slices[0] is for label 1

            if bbox is None:
                continue

            # 2) Add padding to bounding box
            row_min = max(0, bbox[0].start - padding)
            row_max = min(img_height, bbox[0].stop + padding)
            col_min = max(0, bbox[1].start - padding)
            col_max = min(img_width, bbox[1].stop + padding)

            # Extract the bounding box region from the label array
            region = label_array_int[row_min:row_max, col_min:col_max]

            # Create binary mask for this specific label in the region
            mask_bbox = (region == label_id).astype(np.uint8)

            # Check if cell has enough pixels
            if np.sum(mask_bbox) < min_area:
                continue

            # 3) Find contours in the bounding box
            contours = measure.find_contours(mask_bbox, 0.5)

            if not contours:
                continue

            # Use the longest contour (outer boundary)
            contour = max(contours, key=len)

            # Check minimum points
            if len(contour) < 3:
                continue

            # Approximate polygon to reduce points
            coords = measure.approximate_polygon(contour, tolerance=1.0)

            # Convert to QPointF and offset by bounding box origin to map to original image
            if len(coords) >= 3:
                # coords are (row, col) in bbox space, need to add bbox origin offsets
                points = [
                    QPointF(float(x[1] + col_min), float(x[0] + row_min))
                    for x in coords
                ]
                # Store both the label string and the original mask ID
                polygons.append((points, f"Cell_{int(label_id)}", int(label_id)))

        return polygons

    def extract_polygons_from_shapes(
        self, shape_name: Optional[str] = None
    ) -> List[Tuple[List[QPointF], str]]:
        """
        Extract polygons from shape elements.

        Parameters
        ----------
        shape_name : Optional[str]
            Name of the shape element. If None, uses the first available.

        Returns
        -------
        List[Tuple[List[QPointF], str]]
            List of (polygon_points, label) tuples.
        """
        if not self.get_available_shapes():
            return []

        if shape_name is None:
            shape_name = self.get_available_shapes()[0]

        shapes = self.sdata.shapes[shape_name]

        polygons = []

        for idx, row in shapes.iterrows():
            geom = row.geometry

            if isinstance(geom, ShapelyPolygon):
                # Extract exterior coordinates
                coords = list(geom.exterior.coords)
                points = [QPointF(float(x), float(y)) for x, y in coords]

                # Use index as label if no other identifier
                label = str(idx)
                if "cell_id" in row.index:
                    label = f"Cell_{row['cell_id']}"
                elif "name" in row.index:
                    label = str(row["name"])

                polygons.append((points, label))

        return polygons

    def has_cellpick_annotations(self) -> bool:
        """
        Check if the SpatialData store contains CellPick annotations.

        Returns
        -------
        bool
            True if CellPick annotations are present.
        """
        labels = self.get_available_labels()
        return any(name.startswith("cellpick_") for name in labels)

    def load_cellpick_selected_cells(
        self, all_cell_polygons: List[Tuple[List[Any], str]]
    ) -> List[int]:
        """
        Load selected cell indices from CellPick annotations.

        Matches the selected cell masks to the loaded cell polygons to find their indices.

        Parameters
        ----------
        all_cell_polygons : List[Tuple[List[QPointF], str]]
            All loaded cell polygons with their labels.

        Returns
        -------
        List[int]
            List of selected cell indices (indices into all_cell_polygons).
        """
        if "cellpick_selected_cells" not in self.get_available_labels():
            return []

        labels = self.sdata.labels["cellpick_selected_cells"]
        label_data = labels.compute() if hasattr(labels, "compute") else labels.values
        label_array = np.squeeze(np.asarray(label_data))

        # Get unique label IDs (excluding 0 background)
        unique_ids = np.unique(label_array)
        unique_ids = unique_ids[unique_ids > 0]

        if len(unique_ids) == 0:
            return []

        # Extract centroids of selected cell masks
        selected_centroids = []
        for cell_id in unique_ids:
            ys, xs = np.where(label_array == cell_id)
            if len(xs) > 0:
                centroid = (float(np.mean(xs)), float(np.mean(ys)))
                selected_centroids.append(centroid)

        # Match to loaded polygons by finding closest centroid
        selected_indices = []
        for sel_centroid in selected_centroids:
            best_idx = None
            best_dist = float("inf")

            for idx, (points, label) in enumerate(all_cell_polygons):
                # Compute polygon centroid
                if len(points) > 0:
                    poly_centroid_x = sum(pt.x() for pt in points) / len(points)
                    poly_centroid_y = sum(pt.y() for pt in points) / len(points)

                    # Distance to selected centroid
                    dist = (
                        (poly_centroid_x - sel_centroid[0]) ** 2
                        + (poly_centroid_y - sel_centroid[1]) ** 2
                    ) ** 0.5

                    if dist < best_dist:
                        best_dist = dist
                        best_idx = idx

            # Only add if match is close enough (within 50 pixels)
            if best_idx is not None and best_dist < 50:
                selected_indices.append(best_idx)

        return selected_indices

    def load_cellpick_landmarks(self) -> List[List[QPointF]]:
        """
        Load landmarks from CellPick annotations.

        Returns
        -------
        List[List[QPointF]]
            List of landmark point lists.
        """
        if "cellpick_landmarks" not in self.get_available_labels():
            print("[Load] No cellpick_landmarks found in labels")
            return []

        print("[Load] Loading cellpick_landmarks...")
        labels = self.sdata.labels["cellpick_landmarks"]
        label_data = labels.compute() if hasattr(labels, "compute") else labels.values
        label_array = np.squeeze(np.asarray(label_data))

        landmarks = []
        unique_ids = np.unique(label_array)
        unique_ids = unique_ids[unique_ids > 0]
        print(f"[Load] Found {len(unique_ids)} landmark IDs: {unique_ids}")

        for lnd_id in unique_ids:
            # Create a binary mask for this landmark
            mask = (label_array == lnd_id).astype(np.uint8)

            # Find contours (outline of the region)
            contours = measure.find_contours(mask, 0.5)

            if len(contours) > 0:
                # Use the longest contour
                contour = max(contours, key=len)

                # Simplify the polygon
                simplified = measure.approximate_polygon(contour, tolerance=2.0)

                # Convert to QPointF (contours return row, col, so swap: col=x, row=y)
                points = [QPointF(float(x[1]), float(x[0])) for x in simplified]

                # Ensure we have at least 3 points for a valid polygon
                if len(points) >= 3:
                    print(f"[Load]   Landmark {lnd_id} has {len(points)} points")
                    landmarks.append(points)
                else:
                    print(
                        f"[Load]   Landmark {lnd_id} has too few points ({len(points)}), skipping"
                    )
            else:
                print(f"[Load]   Landmark {lnd_id} has no contours, skipping")

        print(f"[Load] Loaded {len(landmarks)} landmarks")
        return landmarks

    def load_cellpick_active_regions(self) -> List[List[QPointF]]:
        """
        Load active regions from CellPick annotations.

        Returns
        -------
        List[List[QPointF]]
            List of active region point lists.
        """
        if "cellpick_AR" not in self.get_available_labels():
            print("[Load] No cellpick_AR found in labels")
            return []

        print("[Load] Loading cellpick_AR...")
        labels = self.sdata.labels["cellpick_AR"]
        label_data = labels.compute() if hasattr(labels, "compute") else labels.values
        label_array = np.squeeze(np.asarray(label_data))

        active_regions = []
        unique_ids = np.unique(label_array)
        unique_ids = unique_ids[unique_ids > 0]
        print(f"[Load] Found {len(unique_ids)} AR IDs: {unique_ids}")

        for ar_id in unique_ids:
            # Create a binary mask for this AR
            mask = (label_array == ar_id).astype(np.uint8)

            # Find contours (outline of the region)
            contours = measure.find_contours(mask, 0.5)

            if len(contours) > 0:
                # Use the longest contour
                contour = max(contours, key=len)

                # Simplify the polygon
                coords = measure.approximate_polygon(contour, tolerance=2.0)

                # Convert to QPointF (contours return row, col, so swap: col=x, row=y)
                points = [QPointF(float(x[1]), float(x[0])) for x in coords]

                if len(points) >= 3:
                    print(f"[Load]   AR {ar_id} has {len(points)} points")
                    active_regions.append(points)
                else:
                    print(
                        f"[Load]   AR {ar_id} has too few points ({len(points)}), skipping"
                    )
            else:
                print(f"[Load]   AR {ar_id} has no contours, skipping")

        print(f"[Load] Loaded {len(active_regions)} active regions")
        return active_regions

    @staticmethod
    def load_labels_from_csv(csv_path: str) -> Dict[int, Any]:
        """
        Load labels from a CSV file.

        The CSV should contain a cell ID column and at least one label column.
        Cell IDs can be 0-based or 1-based; the method will auto-detect and convert.

        Parameters
        ----------
        csv_path : str
            Path to the CSV file.

        Returns
        -------
        Dict[int, Any]
            Dictionary mapping 0-based cell indices to their labels.

        Raises
        ------
        FileNotFoundError
            If the CSV file does not exist.
        ValueError
            If no suitable cell ID column is found.
        """
        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        df = pd.read_csv(csv_file)
        print(f"[CSV Loader] Loaded CSV with shape: {df.shape}")
        print(f"[CSV Loader] Columns: {df.columns.tolist()}")

        # Find cell ID column
        cell_id_col = None
        for col in ["CellID", "cell_id", "Cell_ID", "id", "ID", "cell_index", "index"]:
            if col in df.columns:
                cell_id_col = col
                break

        if cell_id_col is None:
            raise ValueError(
                f"No cell ID column found. Expected one of: CellID, cell_id, Cell_ID, id, ID, cell_index, index"
            )

        print(f"[CSV Loader] Using cell ID column: {cell_id_col}")

        # Choose a label column heuristically: prefer the non-ID column with the most
        # non-null unique values (avoids accidentally picking an empty metadata column).
        candidate_cols = [c for c in df.columns if c != cell_id_col]
        if not candidate_cols:
            raise ValueError("No label column found in CSV")

        # Score columns by number of non-null unique values
        best_col = None
        best_score = -1
        for col in candidate_cols:
            try:
                series = df[col]
                # count non-null unique values excluding empty strings
                non_null = series.dropna().astype(str).map(lambda s: s.strip())
                non_null = non_null[non_null != ""]
                score = non_null.nunique()
            except Exception:
                score = 0
            if score > best_score:
                best_score = score
                best_col = col

        label_col = best_col
        print(f"[CSV Loader] Using label column: {label_col} (score={best_score})")

        labels_dict = {}
        cell_ids = df[cell_id_col].tolist()
        label_values = df[label_col].tolist()

        # Helper to coerce to int if possible (strings like '1', floats that are integral)
        def _coerce_int(x):
            try:
                if isinstance(x, (int, np.integer)):
                    return int(x)
                if isinstance(x, float) and x.is_integer():
                    return int(x)
                if isinstance(x, str):
                    s = x.strip()
                    if s.isdigit():
                        return int(s)
                    # handle floats in string like '1.0'
                    if s.replace(".", "", 1).isdigit():
                        f = float(s)
                        if f.is_integer():
                            return int(f)
            except Exception:
                pass
            return None

        coerced_ids = [_coerce_int(cid) for cid in cell_ids]
        numeric_ids = [c for c in coerced_ids if c is not None]
        min_id = min(numeric_ids) if numeric_ids else None
        max_id = max(numeric_ids) if numeric_ids else None

        print(f"[CSV Loader] Cell ID range (coerced): {min_id} to {max_id}")

        # Decide indexing: if min_id == 0 -> 0-based, if min_id == 1 -> 1-based -> convert
        use_one_based = False
        if min_id is not None:
            if min_id == 0:
                use_one_based = False
            elif min_id == 1:
                use_one_based = True
            else:
                # heuristic: if max_id equals number of rows, assume 1-based
                if max_id == len(cell_ids):
                    use_one_based = True

        duplicates = {}
        for i, (raw_id, label) in enumerate(zip(cell_ids, label_values)):
            cid = coerced_ids[i]
            if cid is None:
                # non-numeric id: use sequential index
                mapped = len(labels_dict)
            else:
                mapped = cid - 1 if use_one_based else cid

            # Normalize label
            try:
                if pd.isna(label):
                    label = ""
                elif isinstance(label, str):
                    label = label.strip()
            except Exception:
                pass

            if mapped in labels_dict:
                # duplicate assignment
                duplicates.setdefault(mapped, 0)
                duplicates[mapped] += 1

            labels_dict[int(mapped)] = label

        # Logging summary
        try:
            from collections import Counter

            cnt = Counter(labels_dict.values())
            print(
                f"[CSV Loader] Loaded {len(labels_dict)} labels (duplicates: {len(duplicates)})"
            )
            print(f"[CSV Loader] Unique labels ({len(cnt)}): {list(cnt.keys())}")
            print(f"[CSV Loader] Counts per label: {dict(cnt)}")
            print(
                f"[CSV Loader] Sample mapping: {dict(list(labels_dict.items())[:10])}"
            )
        except Exception:
            pass

        return labels_dict


class SpatialDataExporter:
    """
    Exporter for saving CellPick data to SpatialData format.
    """

    @staticmethod
    def export_to_spatialdata(
        input_path: Optional[str],
        output_path: str,
        selected_polygons: List[Any],
        landmarks: Optional[List[List[Any]]] = None,
        active_regions: Optional[List[List[Any]]] = None,
        image_shape: Optional[Tuple[int, int]] = None,
        coordinate_system: str = "global",
        progress_callback: Optional[callable] = None,
        image_channels: Optional[List[Tuple[np.ndarray, str]]] = None,
        all_polygons: Optional[List[Any]] = None,
    ) -> None:
        """
        Export CellPick annotations to SpatialData format.

        Updates an existing SpatialData store with CellPick annotations,
        or creates a new one from scratch if loading from image files.

        Parameters
        ----------
        input_path : Optional[str]
            Path to input .zarr store to update. If None, creates new store.
        output_path : str
            Path where to save the .zarr store.
        selected_polygons : List[Polygon]
            List of selected cell polygons.
        landmarks : Optional[List[List[QPointF]]]
            List of landmark point lists.
        active_regions : Optional[List[List[QPointF]]]
            List of active region point lists.
        image_shape : Optional[Tuple[int, int]]
            Image dimensions (height, width) for creating label masks.
        coordinate_system : str
            Name of the coordinate system.
        image_channels : Optional[List[Tuple[np.ndarray, str]]]
            List of (image_data, channel_name) tuples for creating images from scratch.
        all_polygons : Optional[List[Polygon]]
            All cell polygons (not just selected) for creating segmentation labels.

        Raises
        ------
        ImportError
            If spatialdata is not installed.
        """
        if not SPATIALDATA_AVAILABLE:
            raise ImportError(
                "SpatialData is not installed. "
                "Please install it with: pip install spatialdata spatialdata-io spatialdata-plot"
            )

        from spatialdata.models import Labels2DModel
        from skimage.draw import polygon as draw_polygon
        import time

        output_path = Path(output_path)

        if progress_callback:
            progress_callback("Loading existing data...", 5)

        start_time = time.time()
        print(f"[Export] Starting export to {output_path}")

        # Load existing SpatialData if provided, otherwise create new
        if input_path and Path(input_path).exists():
            print(f"[Export] Loading existing SpatialData from {input_path}")
            sdata = sd.read_zarr(input_path)
            print(f"[Export] Loaded in {time.time() - start_time:.2f}s")
        else:
            print(f"[Export] Creating new SpatialData")
            sdata = sd.SpatialData()

            # If creating from scratch with image channels, add them
            if image_channels:
                from spatialdata.models import Image2DModel

                if progress_callback:
                    progress_callback(
                        f"Adding {len(image_channels)} image channels...", 10
                    )

                print(f"[Export] Adding {len(image_channels)} image channels")

                for ch_data, ch_name in image_channels:
                    # Create xarray DataArray for the channel
                    ch_array = xr.DataArray(
                        ch_data[np.newaxis, :, :],  # Add C dimension
                        dims=["c", "y", "x"],
                        coords={
                            "c": [ch_name],
                            "y": np.arange(ch_data.shape[0]),
                            "x": np.arange(ch_data.shape[1]),
                        },
                    )

                    # Parse as Image2DModel
                    sdata.images[ch_name] = Image2DModel.parse(
                        ch_array, transformations={coordinate_system: Identity()}
                    )
                    print(f"[Export]   Added channel: {ch_name}")

        transformations = {coordinate_system: Identity()}

        # Create label masks if we have image shape
        if image_shape is not None:
            height, width = image_shape
            print(f"[Export] Image shape: {height} x {width}")

            # 0. Create full segmentation mask if all_polygons provided (for IMAGE mode)
            if all_polygons:
                if progress_callback:
                    progress_callback(
                        f"Creating segmentation mask for {len(all_polygons)} cells...",
                        15,
                    )

                step_time = time.time()
                print(
                    f"[Export] Creating full segmentation mask ({len(all_polygons)} cells)"
                )
                segmentation_mask = np.zeros((height, width), dtype=np.uint32)

                for idx, poly in enumerate(all_polygons, start=1):
                    if idx % 100 == 0:
                        elapsed = time.time() - step_time
                        print(
                            f"[Export]   Processed {idx}/{len(all_polygons)} cells ({elapsed:.2f}s)"
                        )
                        if progress_callback:
                            pct = 15 + int(5 * idx / len(all_polygons))
                            progress_callback(
                                f"Creating segmentation: {idx}/{len(all_polygons)} cells...",
                                pct,
                            )

                    coords = [(pt.y(), pt.x()) for pt in poly.points]
                    if len(coords) >= 3:
                        try:
                            rr, cc = draw_polygon(
                                [c[0] for c in coords],
                                [c[1] for c in coords],
                                shape=(height, width),
                            )
                            segmentation_mask[rr, cc] = idx
                        except Exception as e:
                            print(f"[Export]   Warning: Failed to draw cell {idx}: {e}")
                            continue

                print(
                    f"[Export] Segmentation mask created in {time.time() - step_time:.2f}s"
                )

                # Add as labels
                seg_da = xr.DataArray(
                    segmentation_mask,
                    dims=["y", "x"],
                    coords={"y": np.arange(height), "x": np.arange(width)},
                )
                sdata.labels["cells"] = Labels2DModel.parse(
                    seg_da, transformations=transformations
                )

            # 1. Create mask for selected cells
            if selected_polygons:
                if progress_callback:
                    progress_callback(
                        f"Creating mask for {len(selected_polygons)} cells...", 20
                    )

                step_time = time.time()
                print(
                    f"[Export] Creating selected cells mask ({len(selected_polygons)} cells)"
                )
                selected_mask = np.zeros((height, width), dtype=np.uint32)

                for idx, poly in enumerate(selected_polygons, start=1):
                    if idx % 50 == 0:
                        elapsed = time.time() - step_time
                        print(
                            f"[Export]   Processed {idx}/{len(selected_polygons)} cells ({elapsed:.2f}s)"
                        )
                        if progress_callback:
                            pct = 20 + int(20 * idx / len(selected_polygons))
                            progress_callback(
                                f"Creating mask: {idx}/{len(selected_polygons)} cells...",
                                pct,
                            )

                    # Convert polygon to mask using polygon fill (MUCH faster than point-by-point)
                    coords = [
                        (pt.y(), pt.x()) for pt in poly.points
                    ]  # (row, col) for skimage
                    if len(coords) >= 3:
                        try:
                            rr, cc = draw_polygon(
                                [c[0] for c in coords],
                                [c[1] for c in coords],
                                shape=(height, width),
                            )
                            selected_mask[rr, cc] = idx
                        except Exception as e:
                            print(
                                f"[Export]   Warning: Failed to draw polygon {idx}: {e}"
                            )
                            continue

                print(
                    f"[Export] Selected cells mask created in {time.time() - step_time:.2f}s"
                )

                # Convert to xarray and add to sdata
                selected_da = xr.DataArray(
                    selected_mask,
                    dims=["y", "x"],
                    coords={"y": np.arange(height), "x": np.arange(width)},
                )
                sdata.labels["cellpick_selected_cells"] = Labels2DModel.parse(
                    selected_da, transformations=transformations
                )

            # 2. Create mask for active regions
            if active_regions:
                if progress_callback:
                    progress_callback(
                        f"Creating mask for {len(active_regions)} ARs...", 50
                    )

                step_time = time.time()
                print(
                    f"[Export] Creating active regions mask ({len(active_regions)} ARs)"
                )
                ar_mask = np.zeros((height, width), dtype=np.uint32)

                for idx, ar_points in enumerate(active_regions, start=1):
                    coords = [(pt.y(), pt.x()) for pt in ar_points]
                    if len(coords) >= 3:
                        try:
                            rr, cc = draw_polygon(
                                [c[0] for c in coords],
                                [c[1] for c in coords],
                                shape=(height, width),
                            )
                            ar_mask[rr, cc] = idx
                        except Exception as e:
                            print(f"[Export]   Warning: Failed to draw AR {idx}: {e}")
                            continue

                print(
                    f"[Export] Active regions mask created in {time.time() - step_time:.2f}s"
                )

                ar_da = xr.DataArray(
                    ar_mask,
                    dims=["y", "x"],
                    coords={"y": np.arange(height), "x": np.arange(width)},
                )
                sdata.labels["cellpick_AR"] = Labels2DModel.parse(
                    ar_da, transformations=transformations
                )

            # 3. Create mask for landmarks (as points/small regions)
            if landmarks:
                if progress_callback:
                    progress_callback(
                        f"Creating mask for {len(landmarks)} landmarks...", 70
                    )

                step_time = time.time()
                print(f"[Export] Creating landmarks mask ({len(landmarks)} landmarks)")
                lnd_mask = np.zeros((height, width), dtype=np.uint32)

                for idx, lnd_points in enumerate(landmarks, start=1):
                    # Convert polygon points to coordinates (y, x)
                    coords = [(pt.y(), pt.x()) for pt in lnd_points]
                    if len(coords) >= 3:
                        try:
                            rr, cc = draw_polygon(
                                [c[0] for c in coords],
                                [c[1] for c in coords],
                                shape=(height, width),
                            )
                            lnd_mask[rr, cc] = idx
                        except Exception as e:
                            print(
                                f"[Export]   Warning: Failed to draw landmark {idx}: {e}"
                            )
                            continue

                print(
                    f"[Export] Landmarks mask created in {time.time() - step_time:.2f}s"
                )

                lnd_da = xr.DataArray(
                    lnd_mask,
                    dims=["y", "x"],
                    coords={"y": np.arange(height), "x": np.arange(width)},
                )
                sdata.labels["cellpick_landmarks"] = Labels2DModel.parse(
                    lnd_da, transformations=transformations
                )

        # Write to disk
        if progress_callback:
            progress_callback("Writing to disk...", 90)

        step_time = time.time()
        print(f"[Export] Writing to disk: {output_path}")
        sdata.write(output_path)
        print(f"[Export] Write completed in {time.time() - step_time:.2f}s")
        print(f"[Export] Total export time: {time.time() - start_time:.2f}s")

    @staticmethod
    def export_table_to_spatialdata(
        sdata_path: str, table_data: pd.DataFrame, table_name: str = "cell_data"
    ) -> None:
        """
        Add a table to an existing SpatialData object.

        Parameters
        ----------
        sdata_path : str
            Path to the .zarr store.
        table_data : pd.DataFrame
            DataFrame to add as a table.
        table_name : str
            Name for the table element.
        """
        if not SPATIALDATA_AVAILABLE:
            raise ImportError("SpatialData is not installed.")

        # Load existing SpatialData
        sdata = sd.read_zarr(sdata_path)

        # Convert to AnnData format (required for SpatialData tables)
        import anndata as ad

        adata = ad.AnnData(obs=table_data)

        # Add spatial coordinates if available
        if "x" in table_data.columns and "y" in table_data.columns:
            spatial_coords = table_data[["x", "y"]].values
            adata.obsm["spatial"] = spatial_coords

        # Add to SpatialData
        sdata.tables[table_name] = adata

        # Write back
        sdata.write(sdata_path)
