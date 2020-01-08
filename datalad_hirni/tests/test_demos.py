# emacs: -*- mode: python-mode; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# -*- coding: utf-8 -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Test demos from documentation"""


import os.path as op
from datalad.api import (
    Dataset,
)
from datalad.tests.utils import (
    assert_result_count,
    assert_in,
    ok_clean_git,
    with_tempfile,
    assert_equal,
    usecase,
    ok_file_under_git,
    assert_repo_status,
    assert_true,
    skip_if_on_windows,
    SkipTest
)


@usecase
@with_tempfile
def test_demo_raw_ds(path):

    ds = Dataset(path)
    ds.create()  # TODO: May be move to ds.create(cfg_proc='hirni') in demo
    ds.run_procedure('cfg_hirni')

    # clean repo with an annex:
    assert_repo_status(ds.repo, annex=True)

    # README, dataset_description.json and studyspec.json at toplevel and in git
    for f in ['README', 'studyspec.json', 'dataset_description.json']:
        ok_file_under_git(ds.path, f, annexed=False)

    # toolbox installed under code/hirni-toolbox
    subs = ds.subdatasets()
    assert_result_count(subs, 1)
    assert_result_count(subs, 1, path=op.join(ds.path, 'code', 'hirni-toolbox'))

    ds.hirni_import_dcm('https://github.com/datalad/example-dicom-structural/archive/master.tar.gz',
                        'acq1',
                        anon_subject='001')

    # acquisition directory and studyspec created + subdataset 'dicoms' within the acquisition dir
    for f in [op.join(ds.path, 'acq1'),
              op.join(ds.path, 'acq1', 'studyspec.json'),
              op.join(ds.path, 'acq1', 'dicoms')
              ]:
        assert_true(op.exists(f))
    subs = ds.subdatasets()
    assert_result_count(subs, 2)
    assert_result_count(subs, 1, path=op.join(ds.path, 'code', 'hirni-toolbox'))
    assert_result_count(subs, 1, path=op.join(ds.path, 'acq1', 'dicoms'))

    # TODO: check actual spec? (Prob. sufficient to test for that in dedicated import-dcm/dcm2spec tests
    # TODO: check dicom metadata

    ds.hirni_import_dcm('https://github.com/datalad/example-dicom-functional/archive/master.tar.gz',
                        'acq2',
                        anon_subject='001')

    # acquisition directory and studyspec created + subdataset 'dicoms' within the acquisition dir
    for f in [op.join(ds.path, 'acq2'),
              op.join(ds.path, 'acq2', 'studyspec.json'),
              op.join(ds.path, 'acq2', 'dicoms')
              ]:
        assert_true(op.exists(f))
    subs = ds.subdatasets()
    assert_result_count(subs, 3)
    assert_result_count(subs, 1, path=op.join(ds.path, 'code', 'hirni-toolbox'))
    assert_result_count(subs, 1, path=op.join(ds.path, 'acq1', 'dicoms'))
    assert_result_count(subs, 1, path=op.join(ds.path, 'acq2', 'dicoms'))

    # Note from demo: The calls to `git annex addurl` and `datalad save` currently replace a single call to
    # `datalad download-url` due to a bug in that command.
    events_file = op.join('acq2', 'events.tsv')
    ds.repo.add_url_to_file(file_=events_file,
                            url='https://github.com/datalad/example-dicom-functional/raw/master/events.tsv')
    ds.save(message="Added stimulation protocol for acquisition 2")

    ok_file_under_git(ds.path, events_file, annexed=True)

    ds.hirni_spec4anything(
        events_file,
        properties='{"procedures": {"procedure-name": "copy-converter", "procedure-call": "bash {script} {{location}} '
                   '{ds}/sub-{{bids-subject}}/func/sub-{{bids-subject}}_task-{{bids-task}}_run-{{bids-run}}_events.tsv'
                   '"}, "type": "events_file"}'
    )

    ok_file_under_git(ds.path, op.join('acq2', 'studyspec.json'), annexed=False)
    assert_repo_status(ds.repo, annex=True)

    # TODO: check spec!
    # compare to:
    # % datalad install -s https://github.com/psychoinformatics-de/hirni-demo --recursive


@skip_if_on_windows  # demo uses bash script
@usecase
@with_tempfile
@with_tempfile
def test_demo_repro_analysis(bids_path, ana_path):

    import glob

    localizer_ds = Dataset(bids_path).create()
    localizer_ds.run_procedure('cfg_bids')
    localizer_ds.install(source="https://github.com/psychoinformatics-de/hirni-demo",
                         path="sourcedata",
                         recursive=True)

    assert_repo_status(localizer_ds.repo)
    subs = localizer_ds.subdatasets(recursive=True)
    assert_result_count(subs, 4)
    assert_result_count(subs, 1, path=op.join(localizer_ds.path, 'sourcedata'))
    assert_result_count(subs, 1, path=op.join(localizer_ds.path, 'sourcedata', 'code', 'hirni-toolbox'))
    assert_result_count(subs, 1, path=op.join(localizer_ds.path, 'sourcedata', 'acq1', 'dicoms'))
    assert_result_count(subs, 1, path=op.join(localizer_ds.path, 'sourcedata', 'acq2', 'dicoms'))

    localizer_ds.hirni_spec2bids([op.join(localizer_ds.path, 'sourcedata', 'studyspec.json')] +
                                 glob.glob(op.join(localizer_ds.path, 'sourcedata', '*', 'studyspec.json')),
                                 anonymize=True)

    for f in ['sub-001',
              'task-oneback_bold.json',
              'participants.tsv',
              op.join('sub-001', 'sub-001_scans.tsv'),
              op.join('sub-001', 'anat'),
              op.join('sub-001', 'anat', 'sub-001_run-1_T1w.json'),
              op.join('sub-001', 'anat', 'sub-001_run-1_T1w.nii.gz'),
              op.join('sub-001', 'func'),
              op.join('sub-001', 'func', 'sub-001_task-oneback_run-01_bold.json'),
              op.join('sub-001', 'func', 'sub-001_task-oneback_run-01_bold.nii.gz'),
              op.join('sub-001', 'func', 'sub-001_task-oneback_run-01_events.tsv'),
              ]:
        assert_true(op.lexists(op.join(localizer_ds.path, f)))

    analysis_ds = Dataset(ana_path).create()
    analysis_ds.install(source=localizer_ds.path, path=op.join('inputs', 'rawdata'))

    analysis_ds.run_procedure('cfg_yoda')
    # download-url expects the target dir to exist
    (analysis_ds.pathobj / 'code').mkdir(exist_ok=True)
    analysis_ds.download_url(
        path=op.join(analysis_ds.path, 'code') + op.sep,  # TODO: File issue. relative path via python API bound method doesn't work
        urls=['https://raw.githubusercontent.com/myyoda/ohbm2018-training/master/section23/scripts/events2ev3.sh',
              'https://raw.githubusercontent.com/myyoda/ohbm2018-training/master/section23/scripts/ffa_design.fsf']
    )

    assert_repo_status(analysis_ds.repo)
    ok_file_under_git(op.join(analysis_ds.path, 'code'), 'events2ev3.sh', annexed=False)
    ok_file_under_git(op.join(analysis_ds.path, 'code'), 'ffa_design.fsf', annexed=False)

    analysis_ds.run(inputs=[op.join('inputs', 'rawdata', 'sub-001', 'func',
                                    'sub-001_task-oneback_run-01_events.tsv')],
                    outputs=[op.join('sub-001', 'onsets')],
                    cmd='bash code/events2ev3.sh sub-001 {inputs}',
                    message="Build FSL EV3 design files"
                    )

    raise SkipTest("Solve datalad-containers #115")

    analysis_ds.containers_add('fsl', url="shub://ReproNim/ohbm2018-training:fsln")
    #   % datalad containers-list

    analysis_ds.save(version_tag="ready4analysis")

    assert_repo_status(analysis_ds.repo)

    #

    analysis_ds.run(
        outputs=[op.join('sub-001', '1stlvl_design.fsf')],
        cmd="bash -c 'sed -e \"s,##BASEPATH##,{pwd},g\" -e \"s,##SUB##,sub-001,g\" code/ffa_design.fsf > {outputs}'",
        message="FSL FEAT analysis config script"
    )

    assert_repo_status(analysis_ds.repo)


    # TODO: Currently failing. Figure it out:
    # analysis_ds.containers_run(
    #     container_name='fsl',
    #     message='sub-001 1st-level GLM',
    #     inputs=[op.join('sub-001', '1stlvl_design.fsf'),
    #             op.join('sub-001', 'onsets'),
    #             op.join('inputs', 'rawdata', 'sub-001', 'func', 'sub-001_task-oneback_run-01_bold.nii.gz')
    #             ],
    #     outputs=[op.join('sub-001', '1stlvl_glm.feat')],
    #     cmd="fsl5.0-feat '{inputs[0]}'"
    # )
    #
    # assert_repo_status(analysis_ds.repo)

# TODO: remaining demo part:
#
# Get Ready for the Afterlife
# ---------------------------
#
# Once a study is complete and published it is important to archive data and results, for example, to be able to respond to inquiries from readers of an associated publication. The modularity of the study units makes this straightforward and avoid needless duplication. We now that the raw data for this GLM analysis is tracked in its own dataset (localizer_scans) that only needs to be archived once, regardless of how many analyses use it as input. This means that we can “throw away” this subdataset copy within this analysis dataset. DataLad can re-obtain the correct version at any point in the future, as long as the recorded location remains accessible.
# We can use the `datalad diff` command and `git log` to verify that the subdataset is in the same state as when it was initially added. Then use datalad uninstall to delete it::
#
#   % datalad diff -- inputs/rawdata
#   % git log -- inputs/rawdata
#   % datalad uninstall --dataset . inputs/rawdata --recursive
#
# Before we archive these analysis results, we can go one step further and verify their computational reproducibility. DataLad provides a rerun command that is capable of “replaying” any recorded command. The following command we re-execute the FSL analysis (the command that was recorded since we tagged the dataset as “ready4analysis”). It will record the recomputed results in a separate Git branch named “verify” of the dataset. We can then automatically compare these new results to the original ones in the “master” branch. We will see that all outputs can be reproduced in bit-identical form. The only changes are observed in log files that contain volatile information, such as time steps::
#
#   # rerun FSL analysis from scratch (~5 min)
#   % datalad rerun --branch verify --onto ready4analysis --since ready4analysis
#   % # check that we are now on the new `verify` branch
#   % git branch
#   % # compare which files have changes with respect to the original results
#   % git diff master --stat
#   % # switch back to the master branch and remove the `verify` branch
#   % git checkout master
#   % git branch -D verify
#
# So, hopefully we've shown that:
#
# - we can implement a complete imaging study using DataLad datasets to represent units of data processing
# - each unit comprehensively captures all inputs and data processing leading up to it
# - this comprehensive capture facilitates re-use of units, and enables computational reproducibility
# - carefully validated intermediate results (captured as a DataLad dataset) are a candidate for publication with minimal additional effort
