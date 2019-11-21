0.4.0 (TBD)
===========

* CI: Fix packaging test (#115) @effigies
* CI: Optimize CircleCI using a local docker registry instead docker save/load (#136) @oesteban
* CI: Run pytests on Python 3.7 for now (#133) @effigies
* CI: Test packaging and update deploy_pypi step (#119) @effigies
* DOC: Deploy docs to gh-pages from CircleCI - with versioning (#65) @rwblair
* DOC: Minimal refactor preparing release (#140) @oesteban
* DOC: Revise numpy docstrings so they are correctly rendered (#134) @oesteban
* ENH: Add --fs-subjects-dir flag (#114) @effigies
* ENH: Add a README.rst (#103) @oesteban
* ENH: Add smriprep-docker wrapper (#118) @effigies
* ENH: Decoupling anatomical reports (#112) @oesteban
* ENH: Reduce friction when iterating over target templates (#111) @oesteban
* ENH: Write out the fsnative-to-T1w transform (#113) @oesteban
* FIX: Build smriprep-docker like fmriprep-docker (#138) @oesteban
* FIX: Check template identifiers are valid early (#135) @oesteban
* FIX: Normalization workflow API - provide bare template names (#139) @oesteban
* FIX: Re-organize FreeSurfer stages to avoid duplication and races (#117) @effigies
* FIX: Revise naming of transforms when several T1w images are averaged (#106) @oesteban
* MAINT: Fine-tune versioning extension of sphinx (#121) @oesteban
* MAINT: Refactoring inputs/outputs names and some stylistic changes (#108) @oesteban
* MAINT: Resolve issues with working directory of ds005 on CircleCI (#110) @oesteban
* PIN: niworkflows ~= 1.0.0rc1

0.3.2 (September 9, 2019)
=========================

Bugfix patch-release

* FIX: Render INU-corrected T1w in Segmentation reportlet (#102) @oesteban

0.3.1 (July 21, 2019)
=====================

Minor release to update pinnings of niworkflows and TemplateFlow client.

* PIN: niworkflows-0.10.1 and templateflow-0.4.1
* CI: Fix PyPI deployment (#99) @effigies

0.3.0 (July 12, 2019)
=====================

Minor release to allow dependent tools to upgrade to PyBIDS 0.9 series (minimum 0.9.2).
We've also moved to a ``setup.cfg``-based setup to standardize configuration.

* MAINT: Move to setup.cfg + pyproject.toml (#98) @effigies
* MAINT: Use PyBIDS 0.9.x via niworkflows PR (#94) @effigies

0.2.4 (July 9, 2019)
====================

Several minor improvements on TemplateFlow integration.

* ENH: Use proper resolution in anatomical outputs (#92) @oesteban
* ENH: Indicate what templates were not found in TemplateFlow (#91) @oesteban
* ENH: Pass template specs on to registration workflow (#90) @oesteban

0.2.3 (June 5, 2019)
====================

Enable CLI to set pediatric and infant templates for skull-stripping.

* ENH: Allow template modifiers (a la ``--output-spaces``) in skull-stripping (#89) @oesteban

0.2.2 (June 5, 2019)
====================

Enable latest templates added to TemplateFlow.

* PIN: templateflow-0.3.0, which includes infant/pediatric templates (#88) @oesteban

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

* First functional version after forking from fMRIPrep
