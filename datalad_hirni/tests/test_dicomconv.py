
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

from datalad.api import Dataset
from datalad.tests.utils import assert_result_count
from datalad.tests.utils import ok_clean_git
from datalad.tests.utils import with_tempfile
from datalad.tests.utils import eq_

import datalad_hirni
from datalad_neuroimaging.tests.utils import get_dicom_dataset
from datalad_neuroimaging.tests.utils import get_bids_dataset


@with_tempfile
def test_dicom_metadata_aggregation(path):
    dicoms = get_dicom_dataset('structural')

    ds = Dataset.create(path)
    ds.install(source=dicoms, path='acq100')
    ds.aggregate_metadata(recursive=True)
    res = ds.metadata(get_aggregates=True)
    assert_result_count(res, 2)
    assert_result_count(res, 1, path=op.join(ds.path, 'acq100'))


@with_tempfile
def test_dicom2spec(path):

    # ###  SETUP ###
    dicoms = get_dicom_dataset('structural')

    ds = Dataset.create(path)
    ds.install(source=dicoms, path='acq100')
    ds.aggregate_metadata(recursive=True, update_mode='all')
    # ### END SETUP ###

    res = ds.hirni_dicom2spec(path='acq100', spec='spec_structural.json')
    assert_result_count(res, 1)
    assert_result_count(res, 1, path=op.join(ds.path, 'spec_structural.json'))
    if ds.repo.is_direct_mode():
        # Note:
        # in direct mode we got an issue determining whether or not sth is
        # "dirty". In this particular case, this is about having a superdataset
        # in direct mode, while the subdataset is a plain git repo.
        # However, at least assert both are clean themselves:
        ok_clean_git(ds.path, ignore_submodules=True)
        ok_clean_git(op.join(ds.path, 'acq100'))

    else:
        ok_clean_git(ds.path)


@with_tempfile
def _single_session_dicom2bids(label, path):

    ds = Dataset.create(path)

    subject = "02"
    acquisition = "{sub}_{label}".format(sub=subject, label=label)

    dicoms = get_dicom_dataset(label)
    ds.install(source=dicoms, path=op.join(acquisition, 'dicoms'))
    ds.aggregate_metadata(recursive=True, update_mode='all')

    spec_file = 'spec_{label}.json'.format(label=label)
    ds.hirni_dicom2spec(path=op.join(acquisition, 'dicoms'),
                        spec=op.join(acquisition, spec_file))

    from datalad_container import containers_add
    ds.containers_add(name="conversion",
                      url="shub://mih/ohbm2018-training:heudiconv")

    ds.hirni_spec2bids(specfile=spec_file)


def test_dicom2bids():
    for l in ['structural', 'functional']:
        yield _single_session_dicom2bids, l


def test_validate_bids_fixture():
    bids_ds = get_bids_dataset()
    # dicom source dataset is absent
    eq_(len(bids_ds.subdatasets(fulfilled=True, return_type='list')), 0)


@with_tempfile
@with_tempfile
def test_spec2bids(study_path, bids_path):

    study_ds = Dataset.hirni_create_study(study_path)

    subject = "02"
    acquisition = "{sub}_functional".format(sub=subject)

    dicoms = get_dicom_dataset('functional')
    study_ds.install(source=dicoms, path=op.join(acquisition, 'dicoms'))
    study_ds.aggregate_metadata(recursive=True, update_mode='all')

    spec_file = 'spec_functional.json'
    study_ds.hirni_dicom2spec(path=op.join(acquisition, 'dicoms'),
                              spec=op.join(acquisition, spec_file))

    # add a custom converter script which is just a copy converter
    makedirs(op.join(study_ds.path, 'code'))
    from shutil import copy
    copy(op.join(op.dirname(datalad_hirni.__file__),
                 'resources', 'dummy_executable.sh'),
         op.join(study_ds.path, 'code', 'my_script.sh'))
    study_ds.add(op.join('code', 'my_script.sh'), to_git=True,
                 message="add a copy converter script")

    # add dummy data to be 'converted' by the copy converter
    makedirs(op.join(study_ds.path, acquisition, 'my_fancy_data'))
    with open(op.join(study_ds.path, acquisition, 'my_fancy_data',
                      'my_raw_data.txt'), 'w') as f:
        f.write("some content")
    study_ds.add(op.join(study_ds.path, acquisition, 'my_fancy_data',
                         'my_raw_data.txt'),
                 message="added fancy data")

    # add specification snippet for that data:
    snippet = {"type": "my_new_type",
               "location": op.join('my_fancy_data', 'my_raw_data.txt'),
               "subject": {"value": "{sub}".format(sub=subject),
                           "approved": True},
               "converter": {"value": "{_hs[converter_path]} {_hs[location]} {dspath}/sub-{_hs[bids_subject]}/my_converted_data.txt",
                             "approved": True},
               "converter_path": {"value": op.join(op.pardir, 'code', 'my_script.sh'),
                                  "approved": True}
               }

    # TODO: proper spec save helper, not just sort (also to be used in webapp!)
    from datalad.support import json_py
    spec_list = [r for r in json_py.load_stream(op.join(study_ds.path, acquisition, spec_file))]
    spec_list.append(snippet)
    from ..support.helpers import sort_spec
    spec_list = sorted(spec_list, key=lambda x: sort_spec(x))
    json_py.dump2stream(spec_list, op.join(study_ds.path, acquisition, spec_file))

    study_ds.add(op.join(acquisition, spec_file),
                 message="Add spec snippet for fancy data",
                 to_git=True)

    # create the BIDS dataset:
    bids_ds = Dataset.create(bids_path)

    # get heudiconv container:
    from datalad_container import containers_add
    bids_ds.containers_add(name="conversion",
                           url="shub://mih/ohbm2018-training:heudiconv")

    # install the study dataset as "sourcedata":
    bids_ds.install(source=study_ds.path, path="sourcedata")

    # make sure, we have the target directory "sub-02" for the copy converter,
    # even if heudiconv didn't run before (order of execution of the converters
    # depends on order in the spec). This could of course also be part of the
    # converter script itself.
    makedirs(op.join(bids_ds.path, "sub-{sub}".format(sub=subject)))

    bids_ds.hirni_spec2bids(op.join("sourcedata", acquisition, spec_file))

    assert op.exists(op.join(bids_ds.path, "sub-{sub}".format(sub=subject), "my_converted_data.txt"))
    with open(op.join(bids_ds.path, "sub-{sub}".format(sub=subject), "my_converted_data.txt"), 'r') as f:
        assert f.readline() == "some content"
