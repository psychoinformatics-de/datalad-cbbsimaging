"""DataLad extension for CBBS imaging platform workflows"""

__docformat__ = 'restructuredtext'

import os.path as op
from os.path import curdir
from os.path import abspath

from datalad.interface.base import Interface
from datalad.interface.base import build_doc
from datalad.support.param import Parameter
from datalad.distribution.dataset import datasetmethod
from datalad.interface.utils import eval_results
from datalad.support.constraints import EnsureChoice

from datalad.interface.results import get_status_dict

# defines a datalad command suite
# this symbol must be identified as a setuptools entrypoint
# to be found by datalad
command_suite = (
    # description of the command suite, displayed in cmdline help
    "HIRNI workflows",
    [
        # specification of a command, any number of commands can be defined
        (
            'datalad_hirni.commands.import_dicoms',
            'ImportDicoms',
            'hirni-import-dcm',
            'hirni_import_dcm',
        ),
        (
            'datalad_hirni.commands.spec4anything',
            'Spec4Anything',
            'hirni-spec4anything',
            'hirni_spec4anything',
        ),
        (
            'datalad_hirni.commands.dicom2spec',
            'Dicom2Spec',
            'hirni-dicom2spec',
            'hirni_dicom2spec',
        ),
        (
            'datalad_hirni.commands.spec2bids',
            'Spec2Bids',
            'hirni-spec2bids',
            'hirni_spec2bids',
        ),
    ]
)

webapp_location = op.join('resources', 'webapp')

from datalad import setup_package
from datalad import teardown_package

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

