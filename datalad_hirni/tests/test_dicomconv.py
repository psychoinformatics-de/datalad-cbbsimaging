# emacs: -*- mode: python-mode; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# -*- coding: utf-8 -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Test DICOM conversion tools"""

import os.path as op
from os import makedirs
from unittest.mock import patch

from datalad.api import Dataset
from datalad.utils import opj
from datalad.tests.utils import (
    assert_result_count,
    eq_,
    with_tempfile
)

import datalad_hirni
from datalad_hirni.tests.utils import cached_url, cached_dataset
from datalad_hirni.tests import HIRNI_TOOLBOX_URL
from datalad_neuroimaging.tests.utils import get_dicom_dataset
from datalad_neuroimaging.tests.utils import get_bids_dataset


@with_tempfile
def test_dicom_metadata_aggregation(path):
    dicoms = get_dicom_dataset('structural')

    ds = Dataset.create(path)
    ds.install(source=dicoms, path='acq100')

    # Note: Recursive, since aggregation wasn't performed in the installed dastasets
    ds.meta_aggregate('acq100', into='top', recursive=True)
    res = ds.meta_dump(reporton='aggregates', recursive=True)
    assert_result_count(res, 2)
    assert_result_count(res, 1, path=op.join(ds.path, 'acq100'))


@with_tempfile
@cached_url(url=HIRNI_TOOLBOX_URL,
            keys=["MD5E-s413687839--c66e63b502702b363715faff763b7968.simg",
                  "MD5E-s304050207--43552f641fd9b518a8c4179a4d816e8e.simg",
                  "MD5E-s273367071--4984c01e667b38d206a9a36acf5721be.simg"])
# @cached_dataset(url="https://github.com/psychoinformatics-de/hirni-toolbox.git",
#                 paths=[opj("converters", "heudiconv", "heudiconv.simg"),
#                        opj("postprocessing", "defacing",
#                            "mridefacer", "mridefacer.simg"),
#                        opj("postprocessing", "fsl", "fsl.simg")]
#                 )
def _single_session_dicom2bids(label, path, toolbox_url):

    with patch.dict('os.environ',
                    {'DATALAD_HIRNI_TOOLBOX_URL': toolbox_url}):
        ds = Dataset.create(path, cfg_proc=['hirni'])

    subject = "02"
    acquisition = "{sub}_{label}".format(sub=subject, label=label)

    dicoms = get_dicom_dataset(label)
    ds.install(source=dicoms, path=op.join(acquisition, 'dicoms'))
    # Note: Recursive, since aggregation wasn't performed in the installed dastasets
    ds.meta_aggregate(op.join(acquisition, 'dicoms'), into='top', recursive=True)

    spec_file = 'spec_{label}.json'.format(label=label)
    ds.hirni_dicom2spec(path=op.join(acquisition, 'dicoms'),
                        spec=op.join(acquisition, spec_file))

    ds.hirni_spec2bids(op.join(acquisition, spec_file))


def test_dicom2bids():
    for l in ['structural', 'functional']:
        yield _single_session_dicom2bids, l


def test_validate_bids_fixture():
    bids_ds = get_bids_dataset()
    # dicom source dataset is absent
    eq_(len(bids_ds.subdatasets(fulfilled=True, return_type='list')), 0)


@with_tempfile
@with_tempfile
@cached_url(url=HIRNI_TOOLBOX_URL,
            keys=["MD5E-s413687839--c66e63b502702b363715faff763b7968.simg",
                  "MD5E-s304050207--43552f641fd9b518a8c4179a4d816e8e.simg",
                  "MD5E-s273367071--4984c01e667b38d206a9a36acf5721be.simg"])
def test_spec2bids(study_path, bids_path, toolbox_url):

    with patch.dict('os.environ',
                    {'DATALAD_HIRNI_TOOLBOX_URL': toolbox_url}):
        study_ds = Dataset(study_path).create(cfg_proc=['hirni'])

    subject = "02"
    acquisition = "{sub}_functional".format(sub=subject)

    dicoms = get_dicom_dataset('functional')
    study_ds.install(source=dicoms, path=op.join(acquisition, 'dicoms'))
    # Note: Recursive, since aggregation wasn't performed in the installed dastasets
    study_ds.meta_aggregate(op.join(acquisition, 'dicoms'), into='top', recursive=True)

    study_ds.hirni_dicom2spec(path=op.join(acquisition, 'dicoms'),
                              spec=op.join(acquisition, 'studyspec.json'))

    # add a custom converter script which is just a copy converter
    from shutil import copy
    copy(op.join(op.dirname(datalad_hirni.__file__),
                 'resources', 'dummy_executable.sh'),
         op.join(study_ds.path, 'code', 'my_script.sh'))
    study_ds.save(op.join('code', 'my_script.sh'), to_git=True,
                  message="add a copy converter script")

    # add dummy data to be 'converted' by the copy converter
    makedirs(op.join(study_ds.path, acquisition, 'my_fancy_data'))
    with open(op.join(study_ds.path, acquisition, 'my_fancy_data',
                      'my_raw_data.txt'), 'w') as f:
        f.write("some content")
    study_ds.save(op.join(study_ds.path, acquisition, 'my_fancy_data', 'my_raw_data.txt'),
                  message="added fancy data")

    # add specification snippet for that data:

    # ############
    # TODO: Needs procedure now
    #
    # snippet = {"type": "my_new_type",
    #            "location": op.join('my_fancy_data', 'my_raw_data.txt'),
    #            "subject": {"value": "{sub}".format(sub=subject),
    #                        "approved": True},
    #            "converter": {"value": "{_hs[converter_path]} {_hs[location]} {dspath}/sub-{_hs[bids_subject]}/my_converted_data.txt",
    #                          "approved": True},
    #            "converter_path": {"value": op.join(op.pardir, 'code', 'my_script.sh'),
    #                               "approved": True}
    #            }
    #
    # # TODO: proper spec save helper, not just sort (also to be used in webapp!)
    # from datalad.support import json_py
    # spec_list = [r for r in json_py.load_stream(op.join(study_ds.path, acquisition, spec_file))]
    # spec_list.append(snippet)
    # from ..support.helpers import sort_spec
    # spec_list = sorted(spec_list, key=lambda x: sort_spec(x))
    # json_py.dump2stream(spec_list, op.join(study_ds.path, acquisition, spec_file))
    #
    # study_ds.add(op.join(acquisition, spec_file),
    #              message="Add spec snippet for fancy data",
    #              to_git=True)
    #
    # ##############

    # create the BIDS dataset:
    with patch.dict('os.environ',
                    {'DATALAD_HIRNI_TOOLBOX_URL': toolbox_url}):
        bids_ds = Dataset.create(bids_path, cfg_proc=['hirni'])

    # install the study dataset as "sourcedata":
    bids_ds.install(source=study_ds.path, path="sourcedata")
    # get the toolbox, since procedures can't be discovered otherwise
    bids_ds.get(op.join('sourcedata', 'code', 'hirni-toolbox', 'converters',
                        'heudiconv', 'heudiconv.simg'))

    # make sure, we have the target directory "sub-02" for the copy converter,
    # even if heudiconv didn't run before (order of execution of the converters
    # depends on order in the spec). This could of course also be part of the
    # converter script itself.
    makedirs(op.join(bids_ds.path, "sub-{sub}".format(sub=subject)))

    bids_ds.hirni_spec2bids(op.join("sourcedata", acquisition, "studyspec.json"))

    # TODO: invalid assertion ATM
    # assert op.exists(op.join(bids_ds.path, "sub-{sub}".format(sub=subject), "my_converted_data.txt"))
    # with open(op.join(bids_ds.path, "sub-{sub}".format(sub=subject), "my_converted_data.txt"), 'r') as f:
    #     assert f.readline() == "some content"
