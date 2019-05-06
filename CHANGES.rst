0.2.1 (May 6, 2019)
===================

Hotfix release improving the reliability of the brain extraction workflow.

* FIX: Keep header consistency along anatomical workflow (#83) @oesteban

0.2.0 (May 3, 2019)
===================

This new release of sMRIPrep adds the possibility of specifying several
spatial normalization targets via the ``--output-spaces`` option drafted
in `poldracklab/fmriprep#1588 <https://github.com/poldracklab/fmriprep/issues/1588>`__.

* ENH: Force compression of derivative NIfTI volumes (#80) @effigies
* DOC/STY: Fix documentation build, simplify (non)parametric output nodes (#79) @oesteban
* FIX: Resolve behavior when deprecated ``--template`` is given (#77) @oesteban
* ENH: Pull list of spatial normalization templates from TemplateFlow (#68) @oesteban
* ENH: CLI uses ``pathlib.Path`` when possible (#73) @oesteban
* ENH: Create a spatial normalization workflow (#72) @oesteban
* ENH: Several improvements over the new spatial normalization workflow (#74) @oesteban
* ENH: Support for multiple ``--output-spaces`` (#75) @oesteban
* FIX: Solved problems in report generation (#76) @oesteban

0.1.1 (March 22, 2019)
======================

* [ENH] Pure Nipype brain extraction workflow (#57) @oesteban
* [ENH] Write metadata for anatomical outputs (#62) @oesteban

0.1.0 (March 05, 2019)
======================

* [PIN] Niworkflows 0.8 and TemplateFlow 0.1 (#56) @oesteban

0.0.5 (February 06, 2019)
=========================

* [MAINT] Update to keep up with poldracklab/niworkflows#299 (#51) @oesteban

0.0.4 (January 25, 2019)
========================

* [DOC] Fix workflow hierarchy within docstrings so that fMRIPrep docs build (`0110ab2 <https://github.com/poldracklab/smriprep/commit/0110ab277faa525d60263ba085947ef1545898af>`__).
* [ENH] Allow templates other than ``MNI152NLin2009cAsym`` (#47) @oesteban


0.0.3 (January 18, 2019)
========================

* [FIX] Add ``-cw256`` flag for images with FoV > 256 voxels (#36) @oesteban
* [ENH] Integrate TemplateFlow to handle templates (#45) @oesteban


0.0.2 (January 8, 2019)
========================

First functional version after forking from fMRIPrep
