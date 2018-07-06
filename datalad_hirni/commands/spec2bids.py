"Convert DICOM data to BIDS based on the respective study specification"

__docformat__ = 'restructuredtext'


import os.path as op
from os.path import isabs
from os.path import join as opj
from os.path import basename
from os.path import lexists
from os.path import relpath

from datalad.interface.base import Interface
from datalad.interface.base import build_doc
from datalad.support.param import Parameter
from datalad.distribution.dataset import datasetmethod
from datalad.distribution.dataset import EnsureDataset
from datalad.distribution.dataset import require_dataset
from datalad.distribution.dataset import resolve_path
from datalad.interface.results import get_status_dict
from datalad.interface.utils import eval_results
from datalad.support.constraints import EnsureStr
from datalad.support.constraints import EnsureNone
from datalad.support.exceptions import InsufficientArgumentsError
from datalad.support.json_py import load_stream
from datalad.utils import assure_list
from datalad.utils import rmtree

from datalad_container import containers_run

import datalad_hirni.support.hirni_heuristic as heuristic

# bound dataset method
import datalad.metadata.aggregate

import logging
lgr = logging.getLogger("datalad.hirni.spec2bids")


def _get_subject_from_spec(file_, anon=False):

    # TODO: this is assuming a session spec snippet.
    # Need to elaborate
    subject_key = 'subject' if not anon else 'anon_subject'
    unique_subs = set([d[subject_key]['value']
                       for d in load_stream(file_)
                       if subject_key in d.keys() and d[subject_key]['value']])
    if not unique_subs:
        raise ValueError("missing %s in %s" % (subject_key, file_))
    if len(unique_subs) > 1:
        raise ValueError("subject ambiguous in %s. candidates: %s" % (file_, unique_subs))
    return unique_subs.pop()


@build_doc
class Spec2Bids(Interface):
    """Convert to BIDS based on study specification
    """

    _params_ = dict(
        dataset=Parameter(
            args=("-d", "--dataset"),
            doc="""bids dataset""",
            constraints=EnsureDataset() | EnsureNone()),
        acquisition_id=Parameter(
            args=("-a", "--acquisition-id",),
            metavar="ACQUISITION_ID",
            nargs="+",
            doc="""name(s)/path(s) of the acquisition(s) to convert.
                like 'sourcedata/ax20_435'""",
            constraints=EnsureStr() | EnsureNone()),
        target_dir=Parameter(
            args=("-t", "--target-dir"),
            doc="""Root dir of the BIDS dataset. Defaults to the root
            dir of the study dataset""",
            constraints=EnsureStr() | EnsureNone()),
        spec_file=Parameter(
            args=("--spec-file",),
            metavar="SPEC_FILE",
            doc="""path to the specification file to use for conversion.
             By default this is a file named 'studyspec.json' in the
             session directory. NOTE: If a relative path is given, it is
             interpreted as a path relative to ACQUISITION_ID's dir (evaluated per
             acquisition). If an absolute path is given, that file is used for all
             acquisitions to be converted!""",
            constraints=EnsureStr() | EnsureNone()),
        anonymize=Parameter(
            args=("--anonymize",),
            action="store_true",
            doc="""whether or not to anonymize for conversion. By now this means
            to use 'anon_subject' instead of 'subject' from spec and to use 
            datalad-run with a sidecar file, to not leak potentially identifying 
            information into its record."""
        )
    )

    @staticmethod
    @datasetmethod(name='hirni_spec2bids')
    @eval_results
    def __call__(acquisition_id=None, dataset=None, target_dir=None,
                 spec_file=None, anonymize=False):

        dataset = require_dataset(dataset, check_installed=True,
                                  purpose="dicoms2bids")

        # TODO: Be more flexible in how to specify the session to be converted.
        #       Plus: Validate (subdataset with dicoms).
        if acquisition_id is not None:
            acquisition_id = assure_list(acquisition_id)
            acquisition_id = [resolve_path(p, dataset) for p in acquisition_id]
        else:
            raise InsufficientArgumentsError(
                "insufficient arguments for spec2bids: a session is required")

        # TODO: check if target dir within dataset. (commit!)
        if target_dir is None:
            target_dir = dataset.path

        if spec_file is None:
            spec_file = "studyspec.json"

        for acq in acquisition_id:

            if isabs(spec_file):
                spec_path = spec_file
            else:
                spec_path = opj(acq, spec_file)

            if not lexists(spec_path):
                yield get_status_dict(
                    action='spec2bids',
                    path=acq,
                    status='impossible',
                    message="Found no spec for acquisition {} at {}".format(acq, spec_path)
                )
                # TODO: onfailure ignore?
                continue
            try:
                # TODO: AutomagicIO?
                dataset.get(spec_path)
                subject = _get_subject_from_spec(spec_path, anon=anonymize)
            except ValueError as e:
                yield get_status_dict(
                    action='spec2bids',
                    path=acq,
                    status='error',
                    message=str(e),
                )
                continue

            from mock import patch
            # relative path to spec to be recorded:
            rel_spec_path = relpath(spec_path, dataset.path) \
                if isabs(spec_path) else spec_path

            # relative path to not-needed-heudiconv output:
            from tempfile import mkdtemp
            rel_trash_path = relpath(mkdtemp(prefix="hirni-tmp-",
                                             dir=opj(dataset.path, ".git")),
                                     dataset.path)

            rel_dicom_path = relpath(opj(acq, 'dicoms'), dataset.path)

            run_results = list()
            with patch.dict('os.environ',
                            {'HIRNI_STUDY_SPEC': rel_spec_path,
                             'HIRNI_SPEC2BIDS_SUBJECT': 'subject'
                             if not anonymize else 'anon_subject'}):

                for r in dataset.containers_run(
                        ['heudiconv',
                         # XXX absolute path will make rerun on other system
                         # impossible -- hard to avoid
                         '-f', heuristic.__file__,
                         # leaves identifying info in run record
                         '-s', subject,
                         '-c', 'dcm2niix',
                         # TODO decide on the fate of .heudiconv/
                         # but ATM we need to (re)move it:
                         # https://github.com/nipy/heudiconv/issues/196
                         '-o', rel_trash_path,
                         '-b',
                         '-a', '{pwd}'
                         if op.realpath(target_dir) == op.realpath(dataset.path) else target_dir,
                         '-l', '',
                         # avoid glory details provided by dcmstack, we have
                         # them in the aggregated DICOM metadata already
                         '--minmeta',
                         '--files', rel_dicom_path
                         ],
                        sidecar=anonymize,
                        container_name="conversion",  # TODO: config
                        inputs=[rel_dicom_path, rel_spec_path],
                        outputs=[target_dir],
                        message="Import DICOM acquisition {}".format(
                            'for subject {}'.format(subject)
                            if anonymize else basename(acq)),
                        return_type='generator',
                ):
                    # if there was an issue with containers-run, yield original
                    # result, otherwise swallow:
                    if r['status'] not in ['ok', 'notneeded']:
                        yield r

                    run_results.append(r)

            if not all(r['status'] in ['ok', 'notneeded'] for r in run_results):
                yield {'action': 'heudiconv',
                       'path': acq,
                       'status': 'error',
                       'message': "acquisition conversion failed. "
                                  "See previous message(s)."}
                return
            else:
                yield {'action': 'heudiconv',
                       'path': acq,
                       'status': 'ok',
                       'message': "acquisition converted."}

            # MIH: Let's not do that, easily done by a user whenever needed,
            # but in the fashion with annex new files on every import
            ## aggregate bids and nifti metadata:
            #for r in dataset.aggregate_metadata(recursive=False,
            #                                    incremental=True):
            #    yield r

            # remove
            rmtree(opj(dataset.path, rel_trash_path))
            yield {'action': 'spec2bids',
                   'path': acq,
                   'status': 'ok'}


