"""Derive a study specification snippet describing a DICOM series based on the
DICOM metadata as provided by datalad.
"""

import logging
import os.path as op

from datalad.core.local.save import Save
from datalad.distribution.dataset import EnsureDataset
from datalad.distribution.dataset import datasetmethod
from datalad.distribution.dataset import require_dataset
from datalad.distribution.dataset import resolve_path
from datalad.interface.base import Interface
from datalad.interface.base import build_doc
from datalad.interface.utils import eval_results
from datalad.support import json_py
from datalad.support.constraints import EnsureNone
from datalad.support.constraints import EnsureStr
from datalad.support.exceptions import InsufficientArgumentsError
from datalad.support.param import Parameter

from datalad_hirni.commands.spec4anything import _get_edit_dict
from datalad_hirni.support.spec_helpers import (
    get_specval,
    has_specval
)

# bound dataset method
import datalad_metalad.dump


lgr = logging.getLogger('datalad.hirni.dicom2spec')


class RuleSet(object):
    """Holds and applies the current rule set for deriving BIDS terms from
    DICOM metadata"""

    def __init__(self, dataset=None):
        """Retrieves the configured set of rules

        Rules are defined by classes ... + __datalad_hirni_rules
        datalad.hirni.dicom2spec.rules  ... multiple

        Parameters
        ----------
        dataset: Dataset
          Dataset to read possibly customized rules from
        """

        from datalad.utils import assure_list
        from datalad import cfg as dl_cfg
        from datalad_hirni.support.default_rules import DefaultRules
        cfg = dataset.config if dataset else dl_cfg

        self._rule_set = []
        # get a list of paths to build the rule set from
        # Note: assure_list is supposed to return empty list if there's nothing
        self._file_list = \
            assure_list(cfg.get("datalad.hirni.dicom2spec.rules"))
        lgr.debug("loaded list of rule files: %s", self._file_list)

        for file in self._file_list:
            if not op.exists(file) or not op.isfile(file):
                lgr.warning("Ignored invalid path for dicom2spec rules "
                            "definition: %s", file)
                continue

            from datalad.utils import import_module_from_file
            from datalad.dochelpers import exc_str
            try:
                mod = import_module_from_file(file)
            except Exception as e:
                # any exception means full stop
                raise ValueError("Rules definition file at {} is broken: {}"
                                 "".format(file, exc_str(e)))

            # check file's __datalad_hirni_rules for the actual class:
            if not hasattr(mod, "__datalad_hirni_rules"):
                raise ValueError("Rules definition file {} missed attribute "
                                 "'__datalad_hirni_rules'.".format(file))
            self._rule_set.append(getattr(mod, "__datalad_hirni_rules"))

        if not self._rule_set:
            self._rule_set = [DefaultRules]

    def apply(self, dicommetadata, subject=None,
              anon_subject=None, session=None):
        """Applies rule set to DICOM metadata

        Note, that a particular series can be determined invalid (for
        application) by those rules, but still needs to show up in the
        specification for later review.

        Parameters
        ----------
        dicommetadata: list of dict
          expects datalad's metadata for DICOMs (the list of dicts for the all
          the series)

        Returns
        -------

        list of dict
          derived dict in specification terminology
        """

        # instantiate rules with metadata; note, that some possible rules might
        # need the entirety of it, not just the current series to be treated.
        actual_rules = [r(dicommetadata) for r in self._rule_set]

        # we want one specification dict per image series
        result_dicts = [dict() for i in range(len(dicommetadata))]

        for rule in actual_rules:

            # TODO: generic overrides instead (or none at all here and let this
            # be done later on - not sure, what's most useful for the rules
            # themselves. Also: If we know already we can save the effort to
            # deduct => likely keep passing on to the rules)
            dict_list = rule(subject=subject,
                             anon_subject=anon_subject,
                             session=session)

            # should return exactly one dict per series:
            assert len(dict_list) == len(dicommetadata)

            for idx, t in zip(range(len(dicommetadata)), dict_list):
                value_dict = t[0]
                is_valid = t[1]
                for key in value_dict.keys():
                    # TODO: This should get more complex (deriving
                    # tags/procedures?) and use some SpecHandler for assignment
                    # (more sophisticated than _get_edit_dict)
                    result_dicts[idx][key] = {'value': value_dict[key],
                                              'approved': False}
                    if not is_valid:
                        if 'tags' in result_dicts[idx] and \
                                'hirni-dicom-converter-ignore' not in \
                                result_dicts[idx]['tags']:
                            result_dicts[idx]['tags'].append('hirni-dicom-converter-ignore')
                        else:
                            result_dicts[idx]['tags'] = ['hirni-dicom-converter-ignore']

        return result_dicts


def add_to_spec(ds_metadata, spec_list, basepath,
                subject=None, anon_subject=None, session=None, overrides=None, dataset=None):

    # TODO: discover procedures and write default config into spec for more convenient editing!
    # But: Would need toolbox present to create a spec. If not - what version of toolbox to use?
    # Double-check run-procedure --discover

    # Spec needs a dicomseries:all snippet before the actual dicomseries
    # snippets, since the order determines the order of execution of procedures
    # later on.
    # Note, that here we only make sure such a snippet exists. It is to be
    # updated with unique values from the dicomseries snippets later on.
    existing_all_dicoms = [i for s, i in zip(spec_list, range(len(spec_list)))
                           if s['type'] == 'dicomseries:all']
    assert len(existing_all_dicoms) <= 1

    if not existing_all_dicoms:
        spec_list.append({'type': 'dicomseries:all'})
        existing_all_dicoms = len(spec_list) - 1
    else:
        existing_all_dicoms = existing_all_dicoms[0]

    # proceed with actual image series:
    lgr.debug("Discovered %s image series.",
              len(ds_metadata['metadata']['dicom']['Series']))

    # generate a list of dicts, with the "rule-proof" entries:
    base_list = []
    for series in ds_metadata['metadata']['dicom']['Series']:
        base_list.append({
            # Note: The first 4 entries aren't a dict and have no
            # "approved flag", since they are automatically managed
            'type': 'dicomseries',
            'location': op.relpath(ds_metadata['path'], basepath),
            'uid': series['SeriesInstanceUID'],
            'dataset-id': ds_metadata['dsid'],
            'dataset-refcommit': ds_metadata['refcommit'],
            'tags': []
            #'tags': ['hirni-dicom-converter-ignore']
            #        if not series_is_valid(series) else [],
        })

    rules_new = RuleSet(dataset=dataset)   # TODO: Pass on dataset for config access! => RF the entire thing
    derived = rules_new.apply(ds_metadata['metadata']['dicom']['Series'],
                              subject=subject,
                              anon_subject=anon_subject,
                              session=session
                              )

    # TODO: Move assertion to a test?
    assert len(derived) == len(base_list)
    for idx in range(len(base_list)):
        base_list[idx].update(derived[idx])

    # merge with existing spec plus overrides:
    for series in base_list:

        series.update(overrides)

        existing = [i for s, i in
                    zip(spec_list, range(len(spec_list)))
                    if s['type'] == 'dicomseries' and s['uid'] == series['uid']]
        if existing:
            lgr.debug("Updating existing spec for image series %s",
                      series['uid'])
            # we already had data of that series in the spec;
            spec_list[existing[0]].update(series)
        else:
            lgr.debug("Creating spec for image series %s", series['uid'])
            spec_list.append(series)

    # spec snippet for addressing an entire dicom acquisition:
    # fill in values of editable fields, that are unique across
    # dicomseries
    uniques = dict()
    for s in spec_list:
        for k in s.keys():
            if isinstance(s[k], dict) and 'value' in s[k]:
                if k not in uniques:
                    uniques[k] = set()
                uniques[k].add(s[k]['value'])

    all_dicoms = dict()
    for k in uniques:
        if len(uniques[k]) == 1:
            all_dicoms[k] = _get_edit_dict(value=uniques[k].pop(),
                                           approved=False)

    all_dicoms.update({
        'type': 'dicomseries:all',
        'location': op.relpath(ds_metadata['path'], basepath),
        'dataset-id': ds_metadata['dsid'],
        'dataset-refcommit': ds_metadata['refcommit'],
        'procedures': [{
                'procedure-name': {'value': 'hirni-dicom-converter',
                                   'approved': False},
                'procedure-call': {'value': None,
                                   'approved': False},
                'on-anonymize': {'value': False,
                                 'approved': False},
            },
        ]
    })

    spec_list[existing_all_dicoms].update(all_dicoms)

    return spec_list


@build_doc
class Dicom2Spec(Interface):
    """Derives a specification snippet from DICOM metadata and stores it in a
    JSON file.

    The derivation is based on a rule system. You can implement your own rules as a python class.
    See the documentation page on customization for details. If you have such rules in dedicated files,
    their use and priority is configured via the datalad.hirni.dicom2spec.rules config variable. It takes
    a path to a python file containung such a rule definition. This configuration can be specified multiple
    times and at different levels (system-wide, user, dataset, local repository). If there are indeed
    several occurences of that configuration, the respective rules will be applied in order. Hence "later"
    appearances will overwrite "earlier" ones. Thereby you can have institution rules for example and still
    apply additional rules tailored to your needs or a particular study.
    """

    _params_ = dict(
            dataset=Parameter(
                    args=("-d", "--dataset"),
                    doc="""specify a dataset containing the DICOM metadata to be 
                    used. If no dataset is given, an attempt is made to identify 
                    the dataset based on the current working directory""",
                    constraints=EnsureDataset() | EnsureNone()),
            path=Parameter(
                    args=("path",),
                    metavar="PATH",
                    nargs="+",
                    doc="""path to DICOM files""",
                    constraints=EnsureStr() | EnsureNone()),
            spec=Parameter(
                    args=("-s", "--spec",),
                    metavar="SPEC",
                    doc="""file to store the specification in""",
                    constraints=EnsureStr() | EnsureNone()),
            subject=Parameter(
                    args=("--subject",),
                    metavar="SUBJECT",
                    doc="""subject identifier. If not specified, an attempt will be made 
                        to derive SUBJECT from DICOM headers""",
                    constraints=EnsureStr() | EnsureNone()),
            anon_subject=Parameter(
                    args=("--anon-subject",),
                    metavar="ANON_SUBJECT",
                    doc="""TODO""",
                    constraints=EnsureStr() | EnsureNone()),
            acquisition=Parameter(
                    args=("--acquisition",),
                    metavar="ACQUISITION",
                    doc="""acquisition identifier. If not specified, an attempt 
                    will be made to derive an identifier from DICOM headers""",
                    constraints=EnsureStr() | EnsureNone()),
            properties=Parameter(
                    args=("--properties",),
                    metavar="PATH or JSON string",
                    doc="""""",
                    constraints=EnsureStr() | EnsureNone()),
    )

    @staticmethod
    @datasetmethod(name='hirni_dicom2spec')
    @eval_results
    def __call__(path=None, spec=None, dataset=None, subject=None,
                 anon_subject=None, acquisition=None, properties=None):

        # TODO: acquisition can probably be removed (or made an alternative to
        # derive spec and/or dicom location from)

        # Change, so path needs to point directly to dicom ds?
        # Or just use acq and remove path?

        dataset = require_dataset(dataset, check_installed=True,
                                  purpose="spec from dicoms")

        from datalad.utils import assure_list
        if path is not None:
            path = assure_list(path)
            path = [resolve_path(p, dataset) for p in path]
            path = [str(p) for p in path]
        else:
            raise InsufficientArgumentsError(
                "insufficient arguments for dicom2spec: a path is required")

        # TODO: We should be able to deal with several paths at once
        #       ATM we aren't (see also commit + message of actual spec)
        assert len(path) == 1

        if not spec:
            raise InsufficientArgumentsError(
                "insufficient arguments for dicom2spec: a spec file is required")

            # TODO: That's prob. wrong. We can derive default spec from acquisition
        else:
            spec = str(resolve_path(spec, dataset))

        spec_series_list = \
            [r for r in json_py.load_stream(spec)] if op.exists(spec) else list()

        # get dataset level metadata:
        found_some = False
        for meta in dataset.meta_dump(
                path,
                recursive=False,  # always False?
                reporton='datasets',
                return_type='generator',
                result_renderer='disabled'):
            if meta.get('status', None) not in ['ok', 'notneeded']:
                yield meta
                continue





            if 'dicom' not in meta['metadata']:

                # TODO: Really "notneeded" or simply not a result at all?
                yield dict(
                        status='notneeded',
                        message=("found no DICOM metadata for %s",
                                 meta['path']),
                        path=meta['path'],
                        type='dataset',
                        action='dicom2spec',
                        logger=lgr)
                continue

            if 'Series' not in meta['metadata']['dicom'] or \
                    not meta['metadata']['dicom']['Series']:
                yield dict(
                        status='impossible',
                        message=("no image series detected in DICOM metadata of"
                                 " %s", meta['path']),
                        path=meta['path'],
                        type='dataset',
                        action='dicom2spec',
                        logger=lgr)
                continue

            found_some = True

            overrides = dict()
            if properties:
                # load from file or json string
                props = json_py.load(properties) \
                        if op.exists(properties) else json_py.loads(properties)
                # turn into editable, pre-approved records
                props = {k: dict(value=v, approved=True) for k, v in props.items()}
                overrides.update(props)

            spec_series_list = add_to_spec(meta,
                                           spec_series_list,
                                           op.dirname(spec),
                                           subject=subject,
                                           anon_subject=anon_subject,
                                           # session=session,
                                           # TODO: parameter "session" was what
                                           # we now call acquisition. This is
                                           # NOT a good default for bids_session!
                                           # Particularly wrt to anonymization
                                           overrides=overrides,
                                           dataset=dataset
                                           )

        if not found_some:
            yield dict(status='impossible',
                       message="found no DICOM metadata",
                       path=path,
                       type='file',  # TODO: arguable should be 'file' or 'dataset', depending on path
                       action='dicom2spec',
                       logger=lgr)
            return

        # TODO: RF needed. This rule should go elsewhere:
        # ignore duplicates (prob. reruns of aborted runs)
        # -> convert highest id only
        # Note: This sorting is a q&d hack!
        # TODO: Sorting needs to become more sophisticated + include notion of :all
        spec_series_list = sorted(spec_series_list,
                                  key=lambda x: get_specval(x, 'id')
                                                if 'id' in x.keys() else 0)
        for i in range(len(spec_series_list)):
            # Note: Removed the following line from condition below,
            # since it appears to be pointless. Value for 'converter'
            # used to be 'heudiconv' or 'ignore' for a 'dicomseries', so
            # it's not clear ATM what case this could possibly have catched:
            # heuristic.has_specval(spec_series_list[i], "converter") and \
            if spec_series_list[i]["type"] == "dicomseries" and \
                has_specval(spec_series_list[i], "bids-run") and \
                get_specval(spec_series_list[i], "bids-run") in \
                    [get_specval(s, "bids-run")
                     for s in spec_series_list[i + 1:]
                     if get_specval(
                            s,
                            "description") == get_specval(
                                spec_series_list[i], "description") and \
                     get_specval(s, "id") > get_specval(
                                             spec_series_list[i], "id")
                     ]:
                lgr.debug("Ignore SeriesNumber %s for conversion" % i)
                spec_series_list[i]["tags"].append(
                        'hirni-dicom-converter-ignore')

        lgr.debug("Storing specification (%s)", spec)
        # store as a stream (one record per file) to be able to
        # easily concat files without having to parse them, or
        # process them line by line without having to fully parse them
        from datalad_hirni.support.spec_helpers import sort_spec
        # Note: Sorting paradigm needs to change. See above.
        # spec_series_list = sorted(spec_series_list, key=lambda x: sort_spec(x))
        json_py.dump2stream(spec_series_list, spec)

        # make sure spec is tracked in git:
        spec_attrs = dataset.repo.get_gitattributes(spec)
        spec_relpath = op.relpath(spec, dataset.path)
        if spec_relpath not in spec_attrs.keys() or \
                'annex.largefiles' not in spec_attrs[spec_relpath].keys() or \
                spec_attrs[spec_relpath]['annex.largefiles'] != 'nothing':
            dataset.repo.set_gitattributes([(spec,
                                             {'annex.largefiles': 'nothing'})],
                                           '.gitattributes')

        for r in Save.__call__(dataset=dataset,
                               path=[spec, '.gitattributes'],
                               to_git=True,
                               message="[HIRNI] Added study specification "
                                       "snippet for %s" %
                                       op.relpath(path[0], dataset.path),
                               return_type='generator',
                               result_renderer='disabled'):
            if r.get('status', None) not in ['ok', 'notneeded']:
                yield r
            elif r['path'] in [spec, op.join(dataset.path, '.gitattributes')] \
                    and r['type'] == 'file':
                r['action'] = 'dicom2spec'
                r['logger'] = lgr
                yield r
            elif r['type'] == 'dataset':
                # 'ok' or 'notneeded' for a dataset is okay, since we commit
                # the spec. But it's not a result to yield
                continue
            else:
                # anything else shouldn't happen
                yield dict(status='error',
                           message=("unexpected result from save: %s", r),
                           path=spec,  # TODO: This actually isn't clear - get it from `r`
                           type='file',
                           action='dicom2spec',
                           logger=lgr)
