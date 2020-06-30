from os.path import join as opj
from unittest.mock import patch
import datalad_hirni
from datalad.api import Dataset

from datalad.tests.utils import (
    ok_exists,
    ok_file_under_git,
    with_tempfile
)
from datalad_hirni.tests.utils import cached_url

from datalad_neuroimaging.tests.utils import create_dicom_tarball


@with_tempfile(mkdir=True)
@with_tempfile
@cached_url(url="https://github.com/psychoinformatics-de/hirni-toolbox.git",
            keys=["MD5E-s164098079--f562d9d23df6359ee3426ca861a6e803.simg",
                  "MD5E-s304050207--43552f641fd9b518a8c4179a4d816e8e.simg",
                  "MD5E-s273367071--4984c01e667b38d206a9a36acf5721be.simg"])
def test_import_tarball(src, ds_path, toolbox_url):

    filename = opj(src, "structural.tar.gz")
    create_dicom_tarball(flavor="structural", path=filename)

    with patch.dict('os.environ',
                    {'DATALAD_HIRNI_TOOLBOX_URL': toolbox_url}):
        ds = Dataset(ds_path).create(cfg_proc=['hirni'])

    # adapt import layout rules for example ds, since hirni default
    # doesn't apply:
    ds.config.set("datalad.hirni.import.acquisition-format",
                  "sub-{PatientID}", where='dataset')

    ds.save(message="TEST: configure acquisition id detection")

    # import into a session defined by the user
    ds.hirni_import_dcm(path=filename, acqid='user_defined_acquisition')

    subs = ds.subdatasets(fulfilled=True, recursive=True, recursion_limit=None,
                          result_xfm='datasets')

    assert opj(ds.path, 'user_defined_acquisition', 'dicoms') in [s.path for s in subs]
    ok_exists(opj(ds.path, 'user_defined_acquisition', 'studyspec.json'))
    ok_file_under_git(opj(ds.path, 'user_defined_acquisition', 'studyspec.json'),
                      annexed=False)
    ok_exists(opj(ds.path, 'user_defined_acquisition', 'dicoms', 'structural'))

    # now import again, but let the import routine figure out an acquisition
    # name based on DICOM metadata (ATM just the first occurring PatientID,
    # I think)
    ds.hirni_import_dcm(path=filename, acqid=None)

    subs = ds.subdatasets(fulfilled=True, recursive=True, recursion_limit=None,
                          result_xfm='datasets')

    assert opj(ds.path, 'sub-02', 'dicoms') in [s.path for s in subs]
    ok_exists(opj(ds.path, 'sub-02', 'studyspec.json'))
    ok_file_under_git(opj(ds.path, 'sub-02', 'studyspec.json'), annexed=False)
    ok_exists(opj(ds.path, 'sub-02', 'dicoms', 'structural'))

