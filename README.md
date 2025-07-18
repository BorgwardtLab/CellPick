
<div align="center">
  
![CellPick Logo](https://raw.githubusercontent.com/BorgwardtLab/CellPick/38cc265d4541407aaed1536e04fc8523a4870f96/cellpick/assets/logo-h.svg)
</div>

<div align="center">
  
[![PyPI version](https://img.shields.io/pypi/v/cellpick.svg?logo=pypi)](https://pypi.org/project/cellpick/)
[![Docs](https://img.shields.io/badge/docs-latest-blue?logo=readthedocs)](https://cellpick.readthedocs.io/en/latest/)
[![Website](https://img.shields.io/badge/website-cellpick.app-44cc11?logo=google-chrome)](https://cellpick.pages.dev/)
</div>

<br>

<br>

**CellPick** is an interactive tool designed to streamline the selection of cells for laser microdissection in single-cell spatial omics applications.  
It features a custom shape selection technique that leverages combinatorial optimization to select non-contiguous cells, maximizing coverage within a defined tissue region.  
CellPick also enables users to establish spatial gradients between landmarks, automatically scoring cells by their proximity to points of interest—facilitating downstream analyses such as correlating protein intensities with spatial location.

For a detailed walkthrough, please refer to the [official documentation](https://cellpick.readthedocs.io/en/latest/).

# Installation

We recommend installing CellPick in an isolated environment using pipx.

You can install pipx using ```pip install pipx```. Running ```pipx ensurepath``` will add pipx (and cellpick) to your PATH.

```bash
pipx install cellpick
```

# Launching the GUI

Once installed, simply launch CellPick from your terminal.

```bash
cellpick
```
