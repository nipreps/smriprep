0.11.1 (March 23, 2023)
=======================
Bug-fix release in the 0.11.1 series.

This release changes the default name of a workflow. This change modifies
the workflow structure superficially, but in such a way that reusing a working
directory should present no possibility of error.

* RF: Reflect function name on nipype workflow (#328)
* DOC: Update boilerplate generation with *TemplateFlow* reference (#329)

0.11.0 (March 10, 2023)
=======================
New feature release in the 0.11.x series.

This series supports fMRIPrep 23.0.x.

This release drops support for Python 3.7.

* ENH: Enable resampling morphometrics to fsLR CIFTI-2 files (#325)
* ENH: Add cortical ribbon workflow (#322)
* ENH: Merge T2w images and coregister to T1w template (#319)
* MAINT: Rotate CircleCI secrets and setup up org-level context (#315)
* CI: Update build to match fMRIPrep (#323)

0.10.0 (November 30, 2022)
==========================
New feature release in the 0.10.x series.

This series supports fMRIPrep 22.1.x and Nibabies 22.2.x.

This will be the last series to support Python 3.7.

* FIX: Expand surfaces pattern to allow morphometrics (#312)
* ENH: Bind FreeSurfer subjects directory (#311)
* ENH: Output thickness, curvature, and sulcal depth files (#305)
* WRAPPER: Update patch location, use --patch syntax (#309)
* CI: Fix expected ds054 outputs (#310)
* CI: Set max Python version to 3.10 (#308)
* CI: Simplify actions to build once, test many (#304)
* CI: Update CircleCI docker orb (#302)

0.9.2 (July 20, 2022)
=====================
Bug-fix release in the 0.9.x series.

With thanks to Eric Feczko for tracking down a fiddly bug.

  * FIX: Use mris_convert --to-scanner, and update normalization step (#295)

0.9.1 (July 14, 2022)
=====================
Bug-fix release in the 0.9.x series.

This release contains patches for supporting FreeSurfer 7.2.

  * FIX: Disable -T2pial and -FLAIRpial at -autorecon1 stage (#291)
  * FIX: Re-add missing getfullpath FreeSurfer binary (#290)
  * FIX: Re-add fsr-checkxopts to Docker image (#287)

0.9.0 (May 26, 2022)
====================
A new minor release incorporating support for FreeSurfer 7.2.

  * DOC: Fix build (#283)
  * DOCKER: Bundle FreeSurfer 7.2 (#281)
  * FIX: Override nipype handling of recon-all hemi input (#282)

0.8.3 (February 08, 2022)
=========================
Patch release in the 0.8.x series. This allows compatibility with the next minor release of `niworkflows`.

  * DOC: Update scipy intersphinx url (#276)
  * MAINT: Allow compatibility with new niworkflows minor (#277)

0.8.2 (December 13, 2021)
=========================
Patch release in the 0.8.x series.

This release includes some minor formatting fixes to the generated workflow boilerplate.
Additionally, the Docker image environment was updated.

  * DOCKER: Update Dockerfile to match fMRIPrep, using FSL 6 (#274)
  * FIX: Generated boilerplate formatting (#275)

0.8.1 (October 08, 2021)
========================
Bug-fix release in the 0.8.x series.

All releases since 0.5.3 have incorrectly resampled the (aparc+)aseg
segmentations with trilinear interpolation, rather than nearest-neighbor.
This fix has also been applied in 0.7.2,
to provide a fix in the fMRIPrep LTS series.

  * FIX: Resample aseg with nearest-neighbor interpolation (#268)

0.8.0 (September 1, 2021)
=========================
A new minor release incorporating small iterations and improvements on
*NiWorkflows*, and including some bug-fixes/enhancements.

* DOC: Ensure copyright notice is found in all Python files (#248)
* FIX: Revert to FAST for tissue probability segmentations (#263)
* FIX: Sturdier version check of sMRIPrep-wrapper package (#245)
* FIX: Do not use deprecated ``--filter pandoc-citeproc`` generating boilerplate (e72eea5)
* FIX: Mask T1w images before transforming to template (#237)
* FIX: Account for label entity when querying brain mask (#257)
* MAINT: Run pytest on GitHub Actions (#262)
* MAINT: Mount TemplateFlow's home directory in CircleCI tests (#246)
* MAINT: Run ``black`` at the top level of the repo (#241)
* MAINT: Update to new API of *NiWorkflows* (#239)
* MAINT: Refactor ``Dockerfile`` and move tests from TravisCI to GHA (#240)
* MAINT: Use separate fallback cache for maint/0.7.x (#250)
* MAINT: CircleCI housekeeping (#258) (#259)

0.7.2 (October 07, 2021)
========================
Bug-fix release in the 0.7.x series.

All releases since 0.5.3 have incorrectly resampled the (aparc+)aseg
segmentations with trilinear interpolation, rather than nearest-neighbor.
This also reverts to using FAST for tissue probability maps, as the
calculations from FreeSurfer's segmentation are less straightforward.

  * FIX: Resample aseg with nearest-neighbor interpolation (#268)
  * FIX: Revert to FAST for tissue probability maps (#264)
  * CI: Use separate fallback cache for maint/0.7.x (#250)

0.7.1 (November 18, 2020)
=========================
Bug-fix release in the 0.7.x series.

All releases since 0.4.0 have incorrectly labelled T1w images normalized to a
template space as SkullStripped in the corresponding JSON sidecar files.
This affects 0.4.x through 0.4.2, 0.5.x through 0.5.3, 0.6.x through 0.6.2, and
0.7.0. Prior to 0.4.0, the images were actually skull-stripped, and the metadata
labels were not incorrect.

For backwards compatibility reasons, any future releases of these series will
have SkullStripped set to False. In 0.8 and above, the images will be skull-stripped
and the metadata set back to True.

* CI: CircleCI housekeeping (#234, #235)

0.7.0 (September 27, 2020)
==========================
Minor release in preparation for *fMRIPrep* 20.2.x LTS series.
Includes minor features and bug-fixes over the previous 0.6 series.

* FIX: Pin *NiWorkflows* 1.3.1 including bugfix for INU-correction failures (nipreps/niworkflows#567)
* FIX: Generate anatomical conversions with full spec from ``--output-spaces`` (#219)
* FIX: Ordering of ``probseg`` maps with anatomical *fast-track* (#214)
* FIX: Progress partial volume maps instead of posteriors (FSL FAST) (#213)
* ENH: Retain session info when multi-session data are not averaged (#225)
* ENH: Update derivatives description, ``.bidsignore`` for derivatives (#220)
* ENH: Add ``--no-tty`` option to Docker wrapper (#216)
* ENH: Add function to handle stale ``IsRunning`` files (#207)
* MAINT: Upgrade ANTs to 2.3.4 in ``Dockerfile`` (365673b)
* MAINT: Make workflows keyword-only (PEP 3102) (#208)

0.6.2 (June 9, 2020)
====================
Bug-fix release addressing minor problems related to FreeSurfer handling.

* FIX: Adapt to the new FS canary interface (backwards compatible) (#205)
* FIX: Use ``t1w2fsnative_xfm`` to resample segmentations (#201)

0.6.1 (May 27, 2020)
====================
Hotfix release to address an issue recently encountered in fMRIPrep 20.1.0rc3.

* FIX: ``MultiLabel`` interpolations should not use ``float=True`` (#196)

0.6.0 (May 22, 2020)
====================
Minor release in preparation for fMRIPrep 20.1.x series.
Features the new implementation of derivatives writers in NiWorkflows,
and additional flexibility to use previously computed results (in particular,
skull-stripped brains, and the new *fast-track* that allows skipping the
anatomical workflow in full, if all the expected derivatives are provided).
Most of the the bug-fixes correspond to amendments over these newly added
features.

* FIX: Convert LTA to ITK with nitransforms (#188)
* FIX: Dismiss ``session`` entity on most of anatomical derivatives (#193)
* FIX: Revise tissue probability maps connections and order (#190)
* FIX: Make TPMs label ordering in ``io_spec.json`` consistent with workflow (#179)
* FIX: Correct the ``dseg`` labeling from FSL FAST earlier (#177)
* FIX: Ensure ``bias_corrected`` is single file, not list (#174)
* ENH: Use new ``DerivativesDataSink`` from NiWorkflows 1.2.0 (#183)
* ENH: Use FreeSurfer's canary to exit fast and with a clear message when the license is missing (#182)
* ENH: Execute FSL FAST only with ``--fs-no-reconall`` (#180)
* ENH: Enable anatomical fast track reusing existing derivatives (#107)
* ENH: Add option to skip brain extraction (#167)
* MAINT: Remove unused nwf interfaces (#187)
* MAINT: Pin troublesome sphinx (#175)
* MAINT: Update dependencies to be inline with fMRIPrep-20.1.x (#173)

0.5.x Series
============
0.5.3 (June 7, 2020)
--------------------
Bug-fix release in the 0.5.x series.

This release fixes a bug where pre-run FreeSurfer that was not in alignment with the
T1w template generated by fMRIPrep could result in misaligned segmentation and mask
derivatives.

The bug is most likely to occur with pre-run FreeSurfer where multiple T1w images are found.
It is easily evident in the first figure in the anatomical section of the reports, and will
show heavily misaligned brain mask.

* FIX: Use t1w2fsnative_xfm to resample segmentations (#201) @effigies

0.5.2 (February 14, 2020)
-------------------------
Minor tweaks in preparation for fMRIPrep 20.0.0 release.

* ENH: Enable users to pass JSON filters to select subsets of data (#143) @bpinsard
* MAINT: Add ignore W503 in setup.cfg (#165) @oesteban

0.5.1 (February 7, 2020)
------------------------
A hotfix release updating dependencies

* PIN: Nibabel 3.0.1 and niworkflows 1.1.6 (#166) @mgxd

0.5.0 (February 6, 2020)
------------------------
A new minor release with a focus on improving internal handling and representations
of spatial references.

* RF: Update Spaces objects (#164) @mgxd
* ENH: Fix template keys output in normalization workflow, when cohort present (#163) @oesteban
* ENH: Integrate new infrastructure in NiWorkflows to handle spatial references (#159) @mgxd
* FIX: Improvements to the CircleCI workflow (#162) @oesteban
* CI: Update coverage (#156) @effigies

Pre- 0.5.x Series
=================
0.4.2 (January 22, 2020)
------------------------
Bugfix release in the 0.4.x series.

* FIX: Calculate FoV with shape and zooms (#161) @effigies
* FIX: Package version incorrect within Docker image (#155) @oesteban
* ENH: Add ``smriprep.__main__`` to allow ``python -m smriprep`` (#158) @effigies
* MAINT: Revise CircleCI to optimize TemplateFlow and caching (#157) @oesteban

0.4.1 (Decemeber 12, 2019)
--------------------------
Bugfix release to address some fMRIPrep issues.

* FIX: Use T2/FLAIR refinement at cortribbon stage (#148) @effigies
* FIX: empty specs for legacy/nonstd spaces (#146) @mgxd
* DOC: Refactor of documentation (#144) @oesteban

0.4.0 (November 26, 2019)
-------------------------
A new 0.4.x series with a number of new features and bugfixes.

* FIX: Allow setting nonstandard spaces for parser (#141) @oesteban
* FIX: Normalization workflow API - provide bare template names (#139) @oesteban
* FIX: Build ``smriprep-docker`` like ``fmriprep-docker`` (#138) @oesteban
* FIX: Check template identifiers are valid early (#135) @oesteban
* FIX: Re-organize FreeSurfer stages to avoid duplication and races (#117) @effigies
* FIX: Revise naming of transforms when several T1w images are averaged (#106) @oesteban
* FIX: Allow setting nonstandard spaces for parser (#141) @oesteban
* ENH: Add ``--fs-subjects-dir`` flag (#114) @effigies
* ENH: Add ``smriprep-docker`` wrapper (#118) @effigies
* ENH: Add a ``README.rst`` (#103) @oesteban
* ENH: Decoupling anatomical reports (#112) @oesteban
* ENH: Reduce friction when iterating over target templates (#111) @oesteban
* ENH: Write out the fsnative-to-T1w transform (#113) @oesteban
* DOC: Minimal refactor preparing release (#140) @oesteban
* DOC: Revise numpy docstrings so they are correctly rendered (#134) @oesteban
* DOC: Deploy docs to gh-pages from CircleCI - with versioning (#65) @rwblair
* CI: Optimize CircleCI using a local docker registry instead docker save/load (#136) @oesteban
* CI: Run pytests on Python 3.7 for now (#133) @effigies
* CI: Fix packaging test (#115) @effigies
* CI: Test packaging and update deploy_pypi step (#119) @effigies
* MAINT: Fine-tune versioning extension of sphinx (#121) @oesteban
* MAINT: Refactoring inputs/outputs names and some stylistic changes (#108) @oesteban
* MAINT: Resolve issues with working directory of ds005 on CircleCI (#110) @oesteban
* PIN: niworkflows ~= 1.0.0rc1

0.3.2 (September 9, 2019)
-------------------------
Bugfix patch-release

* FIX: Render INU-corrected T1w in Segmentation reportlet (#102) @oesteban

0.3.1 (July 21, 2019)
---------------------
Minor release to update pinnings of niworkflows and TemplateFlow client.

* PIN: niworkflows-0.10.1 and templateflow-0.4.1
* CI: Fix PyPI deployment (#99) @effigies

0.3.0 (July 12, 2019)
---------------------
Minor release to allow dependent tools to upgrade to PyBIDS 0.9 series (minimum 0.9.2).
We've also moved to a ``setup.cfg``-based setup to standardize configuration.

* MAINT: Move to setup.cfg + pyproject.toml (#98) @effigies
* MAINT: Use PyBIDS 0.9.x via niworkflows PR (#94) @effigies

0.2.4 (July 9, 2019)
--------------------
Several minor improvements on TemplateFlow integration.

* ENH: Use proper resolution in anatomical outputs (#92) @oesteban
* ENH: Indicate what templates were not found in TemplateFlow (#91) @oesteban
* ENH: Pass template specs on to registration workflow (#90) @oesteban

0.2.3 (June 5, 2019)
--------------------
Enable CLI to set pediatric and infant templates for skull-stripping.

* ENH: Allow template modifiers (a la ``--output-spaces``) in skull-stripping (#89) @oesteban

0.2.2 (June 5, 2019)
--------------------
Enable latest templates added to TemplateFlow.

* PIN: templateflow-0.3.0, which includes infant/pediatric templates (#88) @oesteban

0.2.1 (May 6, 2019)
-------------------
Hotfix release improving the reliability of the brain extraction workflow.

* FIX: Keep header consistency along anatomical workflow (#83) @oesteban

0.2.0 (May 3, 2019)
-------------------
This new release of *sMRIPrep* adds the possibility of specifying several
spatial normalization targets via the ``--output-spaces`` option drafted
in `nipreps/fmriprep#1588 <https://github.com/nipreps/fmriprep/issues/1588>`__.

* FIX: Resolve behavior when deprecated ``--template`` is given (#77) @oesteban
* FIX: Solved problems in report generation (#76) @oesteban
* ENH: Force compression of derivative NIfTI volumes (#80) @effigies
* ENH: Pull list of spatial normalization templates from TemplateFlow (#68) @oesteban
* ENH: CLI uses ``pathlib.Path`` when possible (#73) @oesteban
* ENH: Create a spatial normalization workflow (#72) @oesteban
* ENH: Several improvements over the new spatial normalization workflow (#74) @oesteban
* ENH: Support for multiple ``--output-spaces`` (#75) @oesteban
* DOC/STY: Fix documentation build, simplify (non)parametric output nodes (#79) @oesteban

0.1.1 (March 22, 2019)
----------------------

* ENH: Pure Nipype brain extraction workflow (#57) @oesteban
* ENH: Write metadata for anatomical outputs (#62) @oesteban

0.1.0 (March 05, 2019)
----------------------

* PIN: Niworkflows 0.8 and TemplateFlow 0.1 (#56) @oesteban

0.0.5 (February 06, 2019)
-------------------------

* MAINT: Update to keep up with nipreps/niworkflows#299 (#51) @oesteban

0.0.4 (January 25, 2019)
------------------------

* ENH: Allow templates other than ``MNI152NLin2009cAsym`` (#47) @oesteban
* DOC: Fix workflow hierarchy within docstrings so that fMRIPrep docs build (`0110ab2 <https://github.com/nipreps/smriprep/commit/0110ab277faa525d60263ba085947ef1545898af>`__).

0.0.3 (January 18, 2019)
------------------------

* FIX: Add ``-cw256`` flag for images with FoV > 256 voxels (#36) @oesteban
* ENH: Integrate TemplateFlow to handle templates (#45) @oesteban

0.0.2 (January 8, 2019)
-----------------------

* First functional version after forking from fMRIPrep
