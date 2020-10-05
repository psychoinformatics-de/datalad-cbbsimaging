"""Procedure to apply a sensible default setup to a study dataset
"""

import sys
import os.path as op
import datalad.support.json_py as json_py
from datalad.distribution.dataset import require_dataset

# bound dataset methods
from datalad.api import save
import datalad_hirni.commands.spec4anything
import datalad.distribution.install
from datalad.plugin.add_readme import AddReadme

ds = require_dataset(
    sys.argv[1],
    check_installed=True,
    purpose='study dataset setup')


force_in_git = [
    'README',
    'CHANGES',
    'dataset_description.json',
    '**/{}'.format(ds.config.get("datalad.hirni.studyspec.filename",
                                 "studyspec.json")),
    '**/.git*',
]

# except for hand-picked global metadata, we want anything
# to go into the annex to be able to retract files after
# publication
ds.repo.set_gitattributes([('*', {'annex.backend': 'MD5E'}),
                           ('**', {'annex.largefiles': 'anything'})],
                          mode='w')
ds.repo.set_gitattributes([(p, {'annex.largefiles': 'nothing'})
                           for p in force_in_git])


# TODO:
# Note: This default is using the DICOM's PatientID as the acquisition ID
# (directory name in the study dataset). That approach works for values
# accessible via the DICOM metadata directly. We probably want a way to apply
# more sophisticated rules, which could be achieved by a String Formatter
# providing more sophisticated operations like slicing (prob. to be shared with
# datalad's --output-format logic) or by apply specification rules prior to
# determining final location of the imported subdataset. The latter might lead
# to a mess, since import and specification routines would then be quite
# twisted.
ds.config.add('datalad.hirni.import.acquisition-format',
              "{PatientID}", where='dataset')

# Include an empty dataset_description.json template
bids_description = {
    "Name": "",
    "BIDSVersion": '1.1.1',
    "License": "",
    "Authors": [],
    "Acknowledgements": "",
    "HowToAcknowledge": "",
    "Funding": "",
    "ReferencesAndLinks": [],
    "DatasetDOI": "",
    "Ethics": "",
    "Preregistration": "",
    "Power": "",
}

json_py.dump(bids_description, "./dataset_description.json")

ds.save(message='[HIRNI] Default study dataset configuration')

# Include the most basic README to prevent heudiconv from adding one
# TODO: pointless Warnings on missing metadata from this call if procedure is
# run on an empty dataset:
ds.add_readme(filename='README', existing='fail')

# Add the toolbox as a subdataset
toolbox_url = ds.config.obtain(
        "datalad.hirni.toolbox.url",
        "https://github.com/psychoinformatics-de/hirni-toolbox.git"
)
ds.clone(path=op.join("code", "hirni-toolbox"),
         source=toolbox_url)

# Include a basic top-level spec file, that specifies "copy-conversion" for
# README and dataset_description.json
ds.hirni_spec4anything(path='README',
                       spec_file='studyspec.json',
                       properties={
                           "procedures": {
                               "procedure-name": "copy-converter",
                               "procedure-call": "bash {script} {{location}} {ds}/README"
                                }
                            }
                       )

ds.hirni_spec4anything(path='dataset_description.json',
                       spec_file='studyspec.json',
                       properties={
                           "procedures": {
                               "procedure-name": "copy-converter",
                               "procedure-call": "bash {script} {{location}} {ds}/dataset_description.json"
                                }
                            }
                       )
