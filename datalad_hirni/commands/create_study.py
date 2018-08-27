"""Create a study dataset, that a study's raw data will be imported to.
"""

import logging

from os.path import join as opj

from datalad.interface.base import build_doc
from datalad.distribution.create import Create
from datalad.plugin.add_readme import AddReadme

from datalad.support.constraints import EnsureKeyChoice
from datalad.distribution.dataset import Dataset


lgr = logging.getLogger('datalad.hirni.create_study')


# TODO In my mind this is a mere procedure, like setup_bids_dataset()
# not a full command
@build_doc
class CreateStudy(Create):
    "TODO"

    from datalad.distribution.dataset import datasetmethod
    from datalad.interface.utils import eval_results

    # Note: _params_ inherited from create!

    @staticmethod
    @datasetmethod(name='hirni_create_study')
    @eval_results
    def __call__(
            path=None,
            force=False,
            description=None,
            dataset=None,
            no_annex=False,
            save=True,
            annex_version=None,
            annex_backend='MD5E',
            native_metadata_type=None,
            shared_access=None,
            git_opts=None,
            annex_opts=None,
            annex_init_opts=None,
            text_no_annex=False,  # changed
            fake_dates=False):

        for r in Create.__call__(
                path, force, description,
                dataset, no_annex, save,
                annex_version,
                annex_backend,
                native_metadata_type,
                shared_access, git_opts,
                annex_opts, annex_init_opts,
                text_no_annex,

                # Don't implicitly depend on Create's defaults, but make them
                # explicit instead:
                result_xfm=None,
                return_type='generator',
                result_filter=EnsureKeyChoice('action', ('create',)) & \
                            EnsureKeyChoice('status', ('ok', 'notneeded'))):
            if r['type'] == 'dataset':
                for cr in _cfg_dataset(r):
                    yield cr

            yield r


def _cfg_dataset(r):
    study_ds = Dataset(r['path'])

    with open(opj(study_ds.path, '.gitattributes'), 'a') as ga:
        # except for hand-picked global metadata, we want anything
        # to go into the annex to be able to retract files after
        # publication
        ga.write('** annex.largefiles=anything\n')
        for fn in ('CHANGES', 'README', 'dataset_description.json'):
            # but not these
            ga.write('{} annex.largefiles=nothing\n'.format(fn))
    study_ds.add('.gitattributes', to_git=True,
                 message='Initial annex entry configuration')

    # TODO:
    # Note: This default is quite a hack. It's using the first four
    # characters in DICOM's PatientID as subject and the entire
    # PatientID as session. What's actually needed, is either a
    # String Formatter providing more sophisticated operations like
    # slicing (prob. to be shared with datalad's --output-format
    # logic) or to apply specification rules prior to determining
    # final location of the imported subdataset.
    study_ds.config.add('datalad.hirni.import.acquisition-format',
                        "{PatientID}",
                        where='dataset')

    for r in study_ds.save(message='Initial datalad config'):
        yield r
    # Include the most basic README to prevent heudiconv from adding one
    for r in study_ds.add_readme(filename='README', existing='fail'):
        yield r


########################## CONTAINER TODO: Use datalad-container extension!

    # TODO: get the actual container we are currently in
    #       - requires to get info from outside (via ENV may be)
    #       - but: we do we want to link to the _local_ container?
    #       - may be always add psydata and/or github as a remote
    # datalad run: option + config to use a paricular container
    #              => set env to propagate container's dataset into
    #                 the container itself
    #              => SINGULARITYENV_ prefix
    #
    # datalad run "command" itself needs to set the env and call:
    # THAT_ENV singularity exec configured/container  "command"

    # TODO: Issue: If we clone from psydata, we get a message from
    # datalad-install reading "access to dataset sibling
    # "psydata-store" not auto-enabled, enable with:
    # datalad siblings -d "/tmp/test/.datalad/environments/import-container"
    # enable -s psydata-store
    #
    # => It's actually enabled. Issue comes from distribution/utils:_handle_possible_annex_dataset,
    #    which looks whether that special remote is reported by name.
    #    But it isn't, since it's also 'origin'. We would need to look for annexuuid instead.

    # Note: This is a pointer to the container we are in, if it was
    # passed by the caller (which could be datalad-run) via
    # SINGULARITYENV_DATALAD_CONTAINER:

    # add_sibling_dicts = [{
    #     'action': 'add',
    #     'name': 'github-psyinf',
    #     'url': 'https://github.com/psychoinformatics-de/cbbs-imaging-container-import.git',
    # }]
    #
    # # REMOVE
    # add_sibling_dicts = []
    #
    #
    #
    #
    # container_ds = os.environ.get('DATALAD_CONTAINER')
    # if container_ds:
    #     add_sibling_dicts += {
    #         'action': 'add',
    #         'name': 'psydata',
    #         'url': "http://psydata.ovgu.de/cbbs-imaging/conv-container/.git",
    #         'pushurl': ''
    #     }
    # else:
    #     container_ds = "https://github.com/psychoinformatics-de/cbbs-imaging-container-import.git" #http://psydata.ovgu.de/cbbs-imaging/conv-container/.git"
    #
    #     # REMOVE!
    #     add_sibling_dicts.append({
    #         'action': 'add',
    #         'name': 'psydata',
    #         'url': "http://psydata.ovgu.de/cbbs-imaging/conv-container/.git",
    #         'pushurl': ''
    #     })
    #
    #
    #
    # # What if install fails (no network or sth)?
    #
    # for r_inst in study_ds.install(
    #         path=".datalad/environments/import-container",
    #         source=container_ds,
    #         # TODO: result config
    #         result_xfm=None,
    #         return_type='generator',
    #         result_filter=EnsureKeyChoice('action', ('install',)) & \
    #                     EnsureKeyChoice('status', ('ok', 'notneeded'))
    #         ):
    #     yield r_inst
    #     subds = Dataset(r_inst['path'])
    #
    # for sib in add_sibling_dicts:
    #     # TODO: result config
    #     subds.siblings(**sib)


###############################
