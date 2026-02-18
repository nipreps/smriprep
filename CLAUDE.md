# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

sMRIPrep is a structural MRI preprocessing pipeline in the NiPreps ecosystem (alongside fMRIPrep, dMRIPrep). It preprocesses T1w/T2w/FLAIR anatomical MRI data following BIDS conventions. It uses Nipype workflow engine, FreeSurfer, ANTs, FSL, and Connectome Workbench.

## Common Commands

### Testing
```bash
# Run full test suite (uses pytest-xdist for parallelism)
tox

# Run tests for a specific Python version
tox -e py312-latest

# Run a single test file
pytest test/interfaces/test_surf.py

# Run a single test
pytest test/interfaces/test_surf.py::test_function_name

# Note: default pytest addopts include -svx, --doctest-modules, --cov
# To skip doctests when running a subset:
pytest --override-ini="addopts=" test/interfaces/test_surf.py
```

### Linting and Formatting
```bash
# Check style (ruff lint + format check)
tox -e style

# Auto-fix style issues
tox -e style-fix

# Spell check
tox -e spellcheck

# Direct ruff usage
ruff check --diff
ruff format --diff
```

### Building
```bash
tox -e build
```

## Code Style

- **Formatter/Linter:** Ruff (line length 99, single quotes)
- **Quote style:** Single quotes everywhere
- Black is explicitly disabled

## Architecture

### Source Layout
Uses `src/` layout: all source code lives under `src/smriprep/`.

### Workflow Layer (`workflows/`)
The core of the pipeline. All workflows are Nipype `pe.Workflow` objects built by `init_*_wf()` factory functions.

- **`base.py`** — Top-level orchestrator `init_smriprep_wf()` → creates per-subject workflows
- **`anatomical.py`** — Core anatomical pipeline `init_anat_preproc_wf()`: validation → conformance → bias correction (N4) → skull stripping (ANTs) → segmentation (FAST) → spatial normalization → optional FreeSurfer surface reconstruction
- **`surfaces.py`** — Surface processing: FreeSurfer recon, GIFTI conversion, fsLR registration (MSM), grayordinates (CIFTI), HCP morphometrics
- **`outputs.py`** — BIDS-Derivatives output writing via `DerivativesDataSink`
- **`fit/registration.py`** — Spatial normalization (registration to standard templates)

### Interfaces Layer (`interfaces/`)
Custom Nipype interfaces wrapping external tools (FreeSurfer, FSL, Workbench, MSM) and internal operations (GIFTI/CIFTI manipulation, TemplateFlow queries, surface operations).

### CLI (`cli/run.py`)
BIDS-App compliant command-line interface. Entry point: `smriprep.cli.run:main`.

### Key Ecosystem Dependencies
- **niworkflows** — Shared NiPreps building blocks (brain extraction, image utilities, BIDS I/O)
- **templateflow** — Standardized neuroimaging templates
- **nireports** — Visual QC reports
- **nitransforms** — Spatial transforms

## Naming Conventions (from CONTRIBUTING.md)

- Workflow factory functions: `init_<name>_wf()`
- Workflow variables end in `_wf`
- Node names must match their variable names (aids debugging working directories)
- PR titles use prefixes: `ENH`, `FIX`, `TST`, `DOC`, `STY`, `REF`, `CI`, `MAINT`

## Environment Variables

Key variables passed through tox: `TEMPLATEFLOW_HOME`, `FREESURFER_HOME`, `SUBJECTS_DIR`, `FS_LICENSE`, `TEST_DATA_HOME`, `TEST_OUTPUT_DIR`, `TEST_WORK_DIR`.
