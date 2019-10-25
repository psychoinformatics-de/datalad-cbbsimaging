"""Create specification snippets for arbitrary paths"""


import os.path as op
import posixpath
from six import text_type

from datalad.interface.base import build_doc, Interface
from datalad.support.constraints import EnsureStr
from datalad.support.constraints import EnsureNone
from datalad.support.param import Parameter
from datalad.distribution.dataset import resolve_path
from datalad.distribution.dataset import datasetmethod
from datalad.distribution.dataset import EnsureDataset
from datalad.distribution.dataset import require_dataset
from datalad.interface.utils import eval_results
from datalad.support.network import PathRI
from datalad.support import json_py
from datalad.utils import assure_list
from datalad.interface.annotate_paths import AnnotatePaths
from datalad.interface.results import get_status_dict

# bound dataset method
import datalad_metalad.dump

import logging
lgr = logging.getLogger('datalad.hirni.spec4anything')

# TODO: Prob. should be (partially?) editable, but for now we need consistency
# here:
non_editables = ['location', 'type', 'dataset-id', 'dataset-refcommit']


def _get_edit_dict(value=None, approved=False):
    # our current concept of what an editable field looks like
    return dict(approved=approved, value=value)


def _add_to_spec(spec, spec_dir, path, ds, overrides=None, replace=False):
    """
    Parameters
    ----------
    spec: list of dict
      specification to add the snippet to
    spec_dir:
      path to where the spec file is (paths in spec are relative to that location)
    path:
      path to the entity this snippet is about
    meta:
      metadata of the dataset (for dataset_id and refcommit)
    overrides: dict
      key, values to add/overwrite the default
    """

    from datalad_metalad import get_refcommit
    snippet = {
        'type': 'generic_' + path['type'],
        'location': posixpath.relpath(path['path'], spec_dir),
        'dataset-id': ds.id,
        'dataset-refcommit': get_refcommit(ds),
        'id': _get_edit_dict(),
        'procedures': _get_edit_dict(),
        'comment': _get_edit_dict(value=""),
    }

    snippet.update(overrides)

    # figure, whether we need to append the snippet or replace an
    # existing one
    if replace:
        for s in spec:
            if s['type'] == snippet['type'] and \
               s['location'] == snippet['location'] and \
               s['id']['value'] == snippet['id']['value']:
                # replace existing snippet:
                # Note: This needs to be documented. The identification as well
                # as the fact that only first occurence will be replaced.
                s.update(snippet)
                return spec

    spec.append(snippet)
    return spec


@build_doc
class Spec4Anything(Interface):
    """
    """

    _params_ = dict(
        dataset=Parameter(
            args=("-d", "--dataset"),
            metavar='PATH',
            doc="""specify the dataset. If no dataset is given, an attempt is 
            made to identify the dataset based on the current working directory 
            and/or the `path` given""",
            constraints=EnsureDataset() | EnsureNone()),
        path=Parameter(
            args=("path",),
            metavar='PATH',
            doc="""path(s) of the data to create specification for. Each path
            given will be treated as a data entity getting its own specification 
            snippet""",
            nargs="*",
            constraints=EnsureStr()),
        spec_file=Parameter(
            args=("--spec-file",),
            metavar="SPEC_FILE",
            doc="""path to the specification file to modify.
             By default this is a file named 'studyspec.json' in the
             acquisition directory. This default name can be configured via the
             'datalad.hirni.studyspec.filename' config variable.""",
            constraints=EnsureStr() | EnsureNone()),
        properties=Parameter(
            args=("--properties",),
            metavar="PATH or JSON string",
            # TODO: doc for python API: can also be a dict
            doc="""""",
            constraints=EnsureStr() | EnsureNone()),
        replace=Parameter(
            args=("--replace",),
            action="store_true",
            doc="""if set, replace existing spec if values of 'type', 'location' "
                "and 'id' match. Note, that only the first match will be "
                "replaced.""",

        )
    )

    @staticmethod
    @datasetmethod(name='hirni_spec4anything')
    @eval_results
    def __call__(path, dataset=None, spec_file=None, properties=None,
                 replace=False):
        # TODO: message

        dataset = require_dataset(dataset, check_installed=True,
                                  purpose="hirni spec4anything")
        path = assure_list(path)
        path = [resolve_path(p, dataset) for p in path]
        # TODO: the following is currently necessary, since resolve_path might
        # return PosixPath since datalad0.12.0rc6,
        # while AnnotatePaths and underlying functions would fail to deal
        # with it.
        #       Real solution: Implement hirni commands in new-style
        path = [str(p) for p in path]

        res_kwargs = dict(action='hirni spec4anything', logger=lgr)
        res_kwargs['refds'] = Interface.get_refds_path(dataset)

        # ### This might become superfluous. See datalad-gh-2653
        ds_path = PathRI(dataset.path)
        # ###

        updated_files = []
        paths = []
        for ap in AnnotatePaths.__call__(
                dataset=dataset,
                path=path,
                action='hirni spec4anything',
                unavailable_path_status='impossible',
                nondataset_path_status='error',
                return_type='generator',
                # TODO: Check this one out:
                on_failure='ignore',
                # Note/TODO: Not sure yet whether and when we need those.
                # Generally we want to be able to create a spec for subdatasets,
                # too:
                # recursive=recursive,
                # recursion_limit=recursion_limit,
                # force_subds_discovery=True,
                # force_parentds_discovery=True,
        ):

            if ap.get('status', None) in ['error', 'impossible']:
                yield ap
                continue

            # ### This might become superfluous. See datalad-gh-2653
            ap_path = PathRI(ap['path'])
            # ###

            # find acquisition and respective specification file:
            rel_path = posixpath.relpath(ap_path.posixpath, ds_path.posixpath)

            path_parts = rel_path.split('/')

            # TODO: Note: Outcommented this warning for now. We used to not have
            # a spec file at the toplevel of the study dataset, but now we do.
            # The logic afterwards works, but should be revisited. At least,
            # `acq` should be called differently now.
            # if len(path_parts) < 2:
            #     lgr.warning("Not within an acquisition")
            acq = path_parts[0]

            # TODO: spec file specifiable or fixed path?
            #       if we want the former, what we actually need is an
            #       association of acquisition and its spec path
            #       => prob. not an option but a config

            spec_path = spec_file if spec_file \
                else posixpath.join(ds_path.posixpath, acq,
                                    dataset.config.get("datalad.hirni.studyspec.filename",
                                                       "studyspec.json"))

            spec = [r for r in json_py.load_stream(spec_path)] \
                if posixpath.exists(spec_path) else list()

            lgr.debug("Add specification snippet for %s", ap['path'])
            # XXX 'add' does not seem to be the thing we want to do
            # rather 'set', so we have to check whether a spec for a location
            # is already known and fail or replace it (maybe with --force)

            # go through all existing specs and extract unique value
            # and also assign them to the new record (subjects, ...), but only
            # editable fields!!
            uniques = dict()
            for s in spec:
                for k in s:
                    if isinstance(s[k], dict) and 'value' in s[k]:
                        if k not in uniques:
                            uniques[k] = set()
                        uniques[k].add(s[k]['value'])
            overrides = dict()
            for k in uniques:
                if len(uniques[k]) == 1:
                    overrides[k] = _get_edit_dict(value=uniques[k].pop(),
                                                  approved=False)

            if properties:

                # TODO: This entire reading of properties needs to be RF'd
                # into proper generalized functions.
                # spec got more complex. update() prob. can't simply override
                # (think: 'procedures' and 'tags' prob. need to be appended
                # instead)

                # load from file or json string
                if isinstance(properties, dict):
                    props = properties
                elif op.exists(properties):
                    props = json_py.load(properties)
                else:
                    props = json_py.loads(properties)
                # turn into editable, pre-approved records
                spec_props = {k: dict(value=v, approved=True)
                              for k, v in props.items()
                              if k not in non_editables + ['tags', 'procedures']}
                spec_props.update({k: v
                                   for k, v in props.items()
                                   if k in non_editables + ['tags']})

                # TODO: still wrong. It's a list. Append or override? How to decide?
                spec_props.update({o_k: [{i_k: dict(value=i_v, approved=True)
                                         for i_k, i_v in o_v.items()}]
                                   for o_k, o_v in props.items()
                                   if o_k in ['procedures']})

                overrides.update(spec_props)

            # TODO: It's probably wrong to use uniques for overwriting! At least
            # they cannot be used to overwrite values explicitly set in
            # _add_to_spec like "location", "type", etc.
            #
            # But then: This should concern non-editable fields only, right?

            spec = _add_to_spec(spec, posixpath.split(spec_path)[0], ap,
                                dataset, overrides=overrides, replace=replace)

            # Note: Not sure whether we really want one commit per snippet.
            #       If not - consider:
            #       - What if we fail amidst? => Don't write to file yet.
            #       - What about input paths from different acquisitions?
            #         => store specs per acquisition in memory
            # MIH: One commit per line seems silly. why not update all files
            # collect paths of updated files, and give them to a single `add`
            # at the very end?
            # MIH: if we fail, we fail and nothing is committed
            from datalad_hirni.support.spec_helpers import sort_spec
            json_py.dump2stream(sorted(spec, key=lambda x: sort_spec(x)),
                                spec_path)
            updated_files.append(spec_path)

            yield get_status_dict(
                    status='ok',
                    type=ap['type'],
                    path=ap['path'],
                    **res_kwargs)
            paths.append(ap)

        from datalad.dochelpers import single_or_plural
        from os import linesep
        message = "[HIRNI] Add specification {n_snippets} for: {paths}".format(
                n_snippets=single_or_plural("snippet", "snippets", len(paths)),
                paths=linesep.join(" - " + op.relpath(p['path'], dataset.path)
                                   for p in paths)
                if len(paths) > 1 else op.relpath(paths[0]['path'], dataset.path))
        for r in dataset.save(
                updated_files,
                to_git=True,
                message=message,
                return_type='generator',
                result_renderer='disabled'):
            yield r
