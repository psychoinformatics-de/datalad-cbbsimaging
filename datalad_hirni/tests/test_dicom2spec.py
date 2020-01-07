# emacs: -*- mode: python-mode; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# -*- coding: utf-8 -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Test dicom2spec command; DICOM metadata based specification creation"""

import os.path as op

from datalad.api import (
    Dataset,
    install
)

from datalad.tests.utils import (
    assert_result_count,
    assert_in,
    ok_clean_git,
    with_tempfile,
    assert_equal
)

from datalad.utils import get_tempfile_kwargs

from datalad_neuroimaging.tests.utils import (
    get_dicom_dataset,
)

from datalad.support.json_py import load_stream
from datalad_hirni.support.spec_helpers import (
    get_specval,
    has_specval
)

# TODO:
#
# - invalid calls
# - pass properties
# - test default rules
# - custom vs. configured specfile
# - test results
# - spec file in git? => should stay in git


class RawDataset(object):

    def __init__(self):
        self._dspath = None

    def get_raw_dataset(self):
        # Note: This is lazy to avoid building on import time, since import is part of nose's discovery and executed
        # before the dependencies. This leads to datalad's ui backend not yet being correctly set, which in turn
        # let's the cloning hang within progressbar generation.
        if not self._dspath:
            import tempfile
            kwargs = get_tempfile_kwargs()
            path = tempfile.mkdtemp(**kwargs)
            f_dicoms = get_dicom_dataset('functional')
            s_dicoms = get_dicom_dataset('structural')
            ds = Dataset.create(path, cfg_proc=['hirni'])
            ds.install(source=f_dicoms, path=op.join('func_acq', 'dicoms'))
            ds.install(source=s_dicoms, path=op.join('struct_acq', 'dicoms'))

            # Note: Recursive, since aggregation wasn't performed in the installed dastasets
            ds.meta_aggregate([op.join('func_acq', 'dicoms'), op.join('struct_acq', 'dicoms')],
                              into='top',
                              recursive=True)

            # TODO: Figure how to add it to things to be removed after tests ran
            self._dspath = ds.path
        return self._dspath


test_raw_ds = RawDataset()


@with_tempfile
def test_default_rules(path):

    # ## SETUP a raw ds
    ds = install(source=test_raw_ds.get_raw_dataset(), path=path)
    # ## END SETUP

    # create specs for dicomseries w/ default rules:
    # TODO: spec path should prob. relate to `path` via (derived) acquisition!
    ds.hirni_dicom2spec(path=op.join("func_acq", "dicoms"), spec=op.join("func_acq", "studyspec.json"))
    ds.hirni_dicom2spec(path=op.join("struct_acq", "dicoms"), spec=op.join("struct_acq", "studyspec.json"))

    func_spec = [s for s in load_stream(op.join(path, "func_acq", "studyspec.json"))]

    for snippet in func_spec:
        # type
        assert_in("type", snippet.keys())
        assert_in(snippet["type"], ["dicomseries", "dicomseries:all"])

        # no comment in default spec
        assert not has_specval(snippet, 'comment') or not get_specval(snippet, 'comment')
        # description
        assert has_specval(snippet, 'description')
        assert_equal(get_specval(snippet, 'description'), "func_task-oneback_run-1")
        # subject
        assert has_specval(snippet, 'subject')
        assert_equal(get_specval(snippet, 'subject'), '02')
        # modality
        assert has_specval(snippet, 'bids-modality')
        assert_equal(get_specval(snippet, 'bids-modality'), 'bold')
        # task
        assert has_specval(snippet, "bids-task")
        assert_equal(get_specval(snippet, "bids-task"), "oneback")
        # run
        assert has_specval(snippet, "bids-run")
        assert_equal(get_specval(snippet, "bids-run"), "01")
        # id
        assert has_specval(snippet, "id")
        assert_equal(get_specval(snippet, "id"), 401)

    # should have 1 snippet of type dicomseries + 1 of type dicomseries:all
    assert_equal(len(func_spec), 2)
    assert_in("dicomseries", [s['type'] for s in func_spec])
    assert_in("dicomseries:all", [s['type'] for s in func_spec])

    struct_spec = [s for s in load_stream(op.join(path, "struct_acq", "studyspec.json"))]

    for snippet in struct_spec:

        # type
        assert "type" in snippet.keys()
        assert snippet["type"] in ["dicomseries", "dicomseries:all"]
        # no comment in default spec
        assert not has_specval(snippet, 'comment') or not get_specval(snippet, 'comment')
        # description
        assert has_specval(snippet, 'description')
        assert_equal(get_specval(snippet, 'description'), "anat-T1w")
        # subject
        assert has_specval(snippet, 'subject')
        assert_equal(get_specval(snippet, 'subject'), '02')
        # modality
        assert has_specval(snippet, 'bids-modality')
        assert_equal(get_specval(snippet, 'bids-modality'), 't1w')
        # run
        assert has_specval(snippet, "bids-run")
        assert_equal(get_specval(snippet, "bids-run"), "1")

    # should have 1 snippet of type dicomseries + 1 of type dicomseries:all
    assert_equal(len(struct_spec), 2)
    assert_in("dicomseries", [s['type'] for s in struct_spec])
    assert_in("dicomseries:all", [s['type'] for s in struct_spec])


@with_tempfile
def test_custom_rules(path):

    # ## SETUP a raw ds
    ds = install(source=test_raw_ds.get_raw_dataset(), path=path)
    # ## END SETUP

    # 1. simply default rules
    ds.hirni_dicom2spec(path=op.join("struct_acq", "dicoms"), spec=op.join("struct_acq", "studyspec.json"))
    struct_spec = [s for s in load_stream(op.join(path, "struct_acq", "studyspec.json"))]

    for spec_snippet in struct_spec:

        # no comment in default spec
        assert not has_specval(spec_snippet, 'comment') or not get_specval(spec_snippet, 'comment')
        # subject
        assert has_specval(spec_snippet, 'subject')
        assert_equal(get_specval(spec_snippet, 'subject'), '02')
        # modality
        assert has_specval(spec_snippet, 'bids-modality')
        assert_equal(get_specval(spec_snippet, 'bids-modality'), 't1w')
    # should have 1 snippet of type dicomseries + 1 of type dicomseries:all
    assert_equal(len(struct_spec), 2)
    assert_in("dicomseries", [s['type'] for s in struct_spec])
    assert_in("dicomseries:all", [s['type'] for s in struct_spec])

    # set config to use custom rules
    import datalad_hirni
    ds.config.add("datalad.hirni.dicom2spec.rules",
                  op.join(op.dirname(datalad_hirni.__file__),
                          'resources',
                          'rules',
                          'test_rules.py'),
                  )

    # 2. do again with configured rules (rules 1)
    import os
    os.unlink(op.join(path, 'struct_acq', 'studyspec.json'))

    ds.hirni_dicom2spec(path=op.join("struct_acq", "dicoms"), spec=op.join("struct_acq", "studyspec.json"))
    struct_spec = [s for s in load_stream(op.join(path, "struct_acq", "studyspec.json"))]

    # assertions wrt spec
    for spec_snippet in struct_spec:

        # now there's a comment in spec
        assert has_specval(spec_snippet, 'comment')
        assert_equal(get_specval(spec_snippet, 'comment'), "Rules1: These rules are for unit testing only")

    # should have 1 snippet of type dicomseries + 1 of type dicomseries:all
    assert_equal(len(struct_spec), 2)
    assert_in("dicomseries", [s['type'] for s in struct_spec])
    assert_in("dicomseries:all", [s['type'] for s in struct_spec])

    # 3. once again with two configured rule sets (rules 1 and 2)
    ds.config.add("datalad.hirni.dicom2spec.rules",
                  op.join(op.dirname(datalad_hirni.__file__),
                          'resources',
                          'rules',
                          'test_rules2.py'),
                  )
    rule_files = ds.config.get("datalad.hirni.dicom2spec.rules")
    # ensure assumption about order (dicom2spec relies on it):

    assert_equal(rule_files,
                 (op.join(op.dirname(datalad_hirni.__file__),
                          'resources',
                          'rules',
                          'test_rules.py'),
                  op.join(op.dirname(datalad_hirni.__file__),
                          'resources',
                          'rules',
                          'test_rules2.py')
                  )
                 )

    os.unlink(op.join(path, 'struct_acq', 'studyspec.json'))
    ds.hirni_dicom2spec(path=op.join("struct_acq", "dicoms"), spec=op.join("struct_acq", "studyspec.json"))
    struct_spec = [s for s in load_stream(op.join(path, "struct_acq", "studyspec.json"))]

    # assertions wrt spec
    for spec_snippet in struct_spec:

        # Rule2 should have overwritten Rule1's comment:
        assert has_specval(spec_snippet, 'comment')
        assert_equal(get_specval(spec_snippet, 'comment'), "Rules2: These rules are for unit testing only")

    # should have 1 snippet of type dicomseries + 1 of type dicomseries:all
    assert_equal(len(struct_spec), 2)
    assert_in("dicomseries", [s['type'] for s in struct_spec])
    assert_in("dicomseries:all", [s['type'] for s in struct_spec])


@with_tempfile
def test_dicom2spec(path):

    # ###  SETUP ###
    dicoms = get_dicom_dataset('structural')

    ds = Dataset.create(path, cfg_proc=['hirni'])
    ds.install(source=dicoms, path='acq100')
    # Note: Recursive, since aggregation wasn't performed in the installed dastasets
    # TODO: Use get_raw_sd from above instead of this setup
    ds.meta_aggregate('acq100', into='top', recursive=True)
    # ### END SETUP ###

    # TODO: should it be specfile or acq/specfile? => At least doc needed,
    # if not change
    res = ds.hirni_dicom2spec(path='acq100', spec='spec_structural.json')

    # check for actual location of spec_structural!
    # => studyds root!

    assert_result_count(res, 2)
    assert_result_count(res, 1, path=op.join(ds.path, 'spec_structural.json'))
    assert_result_count(res, 1, path=op.join(ds.path, '.gitattributes'))
    ok_clean_git(ds.path)

    # multiple execution shouldn't change .gitattributes again:
    from os import stat
    mtime = stat(op.join(ds.path, '.gitattributes')).st_mtime
    res = ds.hirni_dicom2spec(path='acq100', spec='spec_structural.json')
    assert_equal(stat(op.join(ds.path, '.gitattributes')).st_mtime, mtime)
