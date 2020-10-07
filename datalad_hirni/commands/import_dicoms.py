"""Import a DICOM tarball into a study dataset"""

from os import listdir
from os import makedirs
from os import rename
import os.path as op
import shutil
from datalad.consts import ARCHIVES_SPECIAL_REMOTE
from datalad.consts import DATALAD_SPECIAL_REMOTES_UUIDS
from datalad.interface.base import build_doc, Interface
from datalad.support.constraints import EnsureStr
from datalad.support.constraints import EnsureNone
from datalad.support.constraints import EnsureKeyChoice
from datalad.support.param import Parameter
from datalad.support.network import get_local_file_url, RI, PathRI
from datalad.distribution.dataset import Dataset
from datalad.distribution.dataset import datasetmethod
from datalad.distribution.dataset import EnsureDataset
from datalad.distribution.dataset import require_dataset
from datalad.interface.utils import eval_results
from datalad.utils import (
    rmtree,
    with_pathsep
)
from datalad.dochelpers import exc_str

# bound dataset method
import datalad_hirni.commands.dicom2spec
import datalad_metalad.aggregate
import datalad_metalad.dump
import datalad.interface.download_url

import logging
lgr = logging.getLogger('datalad.hirni.import_dicoms')


# TODO: Commit-Message to contain hint on the imported tarball
def _import_dicom_tarball(target_ds, tarball, filename):

    current_user_branch = target_ds.repo.get_active_branch()
    # # TODO: doesn't work for updates yet:
    # # - branches are expected to not exist yet
    target_ds.repo.checkout('incoming', options=['-b'])
    target_ds.repo.init_remote(
        ARCHIVES_SPECIAL_REMOTE,
        options=['encryption=none', 'type=external',
                 'externaltype=%s' % ARCHIVES_SPECIAL_REMOTE,
                 'autoenable=true',
                 'uuid={}'.format(
                     DATALAD_SPECIAL_REMOTES_UUIDS[ARCHIVES_SPECIAL_REMOTE])
                 ])

    if isinstance(RI(tarball), PathRI):
        shutil.copy2(tarball, op.join(target_ds.path, filename))
        target_ds.repo.add(filename)

    else:
        target_ds.repo.add_url_to_file(file_=filename, url=tarball, batch=False)

    target_ds.repo.commit(msg="Retrieved %s" % tarball)
    target_ds.repo.checkout('incoming-processed', options=['--orphan'])
    if target_ds.repo.dirty:
        target_ds.repo.remove('.', r=True, f=True)

    target_ds.repo.merge('incoming', options=["-s", "ours", "--no-commit"],
                         expect_stderr=True)
    target_ds.repo._git_custom_command([], "git read-tree -m -u incoming")

    from datalad.coreapi import add_archive_content
    # # TODO: Reconsider value of --existing
    add_archive_content(archive=filename,
                        annex=target_ds.repo,
                        existing='archive-suffix',
                        delete=True,
                        commit=False,
                        allow_dirty=True)

    target_ds.repo.commit(msg="Extracted %s" % tarball)
    target_ds.repo.checkout(current_user_branch)
    target_ds.repo.merge('incoming-processed', options=["--allow-unrelated"])


def _create_subds_from_tarball(tarball, targetdir):

    filename = op.basename(tarball)

    importds = Dataset(op.join(targetdir, "dicoms")).create(
        return_type='item-or-list',
        result_xfm='datasets',
        result_filter=EnsureKeyChoice('action', ('create',)) \
        & EnsureKeyChoice('status', ('ok', 'notneeded'))
    )

    _import_dicom_tarball(importds, tarball, filename)

    importds.config.add(
        var="datalad.metadata.nativetype",
        value="dicom",
        where="dataset"
    )
    importds.config.add(
        var="datalad.metadata.aggregate-content-dicom",
        value='false',
        where="dataset")
    # TODO: file an issue: config.add can't convert False to 'false' on its own
    # (But vice versa while reading IIRC)

    importds.config.add(
        var="datalad.metadata.maxfieldsize",
        value='10000000',
        where="dataset")
    importds.save(op.join(".datalad", "config"),
                  message="[HIRNI] initial config for DICOM metadata")

    return importds


def _guess_acquisition_and_move(ds, target_ds):

    ds.meta_aggregate()
    res = ds.meta_dump(
        reporton='datasets',
        return_type='item-or-list',
        result_renderer='disabled')
    # there should be exactly one result and therefore a dict
    assert isinstance(res, dict)

    # TODO: Move default to config definition
    #       This requires a general mechanism to plugin an extension's config specs
    format_string = \
        target_ds.config.get("datalad.hirni.import.acquisition-format", default="{PatientID}")
    # Note: simply the metadata dict for first Series herein is passed into
    # format ATM.
    # TODO: Eventually make entire result from `metadata` available.
    # (unify implementation with datalad's --output-format)
    if '{' in format_string:
        ses = format_string.format(**res['metadata']['dicom']['Series'][0])
    else:
        ses = format_string

    # `ses` might consist of several levels, so `rename` doesn't always
    # automatically create the target dir:
    if not op.lexists(op.dirname(ses)):
        makedirs(op.join(target_ds.path, ses))

    rename(op.join(target_ds.path, '.git', 'datalad', 'hirni_import'),
           op.join(target_ds.path, ses))

    return Dataset(op.join(target_ds.path, ses, 'dicoms'))


@build_doc
class ImportDicoms(Interface):
    """Import a DICOM archive into a study raw dataset.

    This creates a subdataset, containing the extracted DICOM files, under ACQUISITION ID/dicoms.
    Metadata is extracted from the DICOM headers and a study specification will automatically be prefilled, based on
    the metadata in DICOM headers. The specification is written to AQUISTION ID/studyspec.json by default.
    To this end after the creation of the subdataset and the extraction of DICOM metadata, hirni-dicom2spec is called internally.
    Therefore whatever you configure regarding dicom2spec applies here as well. Please refer to hirni-dicom2spec's documentation
    on how to configure the deduction from DICOM metadata to a study specification."""

    _params_ = dict(
        dataset=Parameter(
            args=("-d", "--dataset"),
            metavar='PATH',
            doc="""specify the dataset to import the DICOM archive into.  If
            no dataset is given, an attempt is made to identify the dataset
            based on the current working directory and/or the given PATH""",
            constraints=EnsureDataset() | EnsureNone()),
        path=Parameter(
            args=("path",),
            metavar='PATH',
            doc="""path or URL of the dicom archive to be imported.""",
            constraints=EnsureStr()),
        acqid=Parameter(
            args=("acqid",),
            metavar="ACQUISITION ID",
            doc="""acquisition identifier for the imported DICOM files. This is used as the name the of directory, that is supposed to contain all data related to that acquisition.
            If not specified, an attempt will be made to derive ACQUISITION_ID from DICOM metadata. You can specify how to deduce that identifier from the DICOM header fields by
            configuring `datalad.hirni.import.acquisition-format` with a python format string referencing DICOM header field names as variables. For example, the current default
            value for that configuration is "{PatientID}".""",
            nargs="?",
            constraints=EnsureStr() | EnsureNone()),
        subject=Parameter(
            args=("--subject",),
            metavar="SUBJECT",
            doc="""subject identifier. If not specified, an attempt will be made
            to derive SUBJECT from DICOM headers. See hirni-dicom2spec for details.""",
            constraints=EnsureStr() | EnsureNone()),
        anon_subject=Parameter(
            args=("--anon-subject",),
            metavar="ANON_SUBJECT",
            doc="""an anonymized subject identifier. This is needed for
            anonymized conversion via spec2bids --anonymize and will be stored
            in the specification snippet for the imported DICOMs. Hence it can
            be added later and isn't mandatory for the import.""",
            constraints=EnsureStr() | EnsureNone()),
        properties=Parameter(
            args=("--properties",),
            metavar="PATH or JSON string",
            doc="""a JSON string or a path to a JSON file, to provide
            overrides/additions to the to be created specification snippets for this acquisition.
            """,
            constraints=EnsureStr() | EnsureNone()),

    )

    @staticmethod
    @datasetmethod(name='hirni_import_dcm')
    @eval_results
    def __call__(path, acqid=None, dataset=None,
                 subject=None, anon_subject=None, properties=None):
        ds = require_dataset(dataset, check_installed=True,
                             purpose="import DICOM session")
        if acqid:
            # acquisition was specified => we know where to create subds
            acq_dir = op.join(ds.path, acqid)
            if not op.exists(acq_dir):
                makedirs(acq_dir)
            # TODO: if exists: needs to be empty?

            dicom_ds = _create_subds_from_tarball(path, acq_dir)

        else:
            # we don't know the acquisition id yet => create in tmp

            acq_dir = op.join(ds.path, '.git', 'datalad', 'hirni_import')
            assert not op.exists(acq_dir)
            # TODO: don't assert; check and adapt instead

            try:
                dicom_ds = _create_subds_from_tarball(path, acq_dir)
                dicom_ds = _guess_acquisition_and_move(dicom_ds, ds)
            except OSError as e:
                # TODO: Was FileExistsError. Find more accurate PY2/3 solution
                # than just OSError
                yield dict(status='impossible',
                           path=e.filename,
                           type='file',
                           action='import DICOM tarball',
                           logger=lgr,
                           message=exc_str(e))
                rmtree(acq_dir)
                return  # we can't do anything
            finally:
                if op.exists(acq_dir):
                    lgr.debug("Killing temp dataset at %s ...", acq_dir)
                    rmtree(acq_dir)

        acqid = op.basename(op.dirname(dicom_ds.path))
        ds.save(
            dicom_ds.path,
            message="[HIRNI] Add aquisition {}".format(acqid)
        )

        # Note: use path with trailing slash to indicate we want metadata about the content of this subds,
        # not the subds itself.
        ds.meta_aggregate(with_pathsep(dicom_ds.path), into='top')

        ds.hirni_dicom2spec(
            path=dicom_ds.path,
            spec=op.normpath(op.join(
                dicom_ds.path, op.pardir, "studyspec.json")),
            subject=subject,
            anon_subject=anon_subject,
            acquisition=acqid,
            properties=properties
        )

        # TODO: This should probably be optional
        # We have the tarball and can drop extracted stuff:
        dicom_ds.drop([f for f in listdir(dicom_ds.path)
                       if f != ".datalad" and f != ".git"])

        # finally clean up git objects:
        dicom_ds.repo.cmd_call_wrapper.run(['git', 'gc'])

        # TODO: yield error results etc.
        yield dict(
            status='ok',
            path=dicom_ds.path,
            type='dataset',
            action='import DICOM tarball',
            logger=lgr)
