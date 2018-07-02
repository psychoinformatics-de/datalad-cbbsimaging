#!/usr/bin/env python

import os.path as op
from setuptools import setup
from setuptools import find_packages
from setuptools import findall

from setup_support import BuildManPage
from setup_support import get_version


def findsome(subdir, extensions):
    """Find files under subdir having specified extensions

    Leading directory (datalad) gets stripped
    """
    return [
        f.split(op.sep, 1)[1]
        for f in findall(op.join('datalad_hirni', subdir))
        if op.splitext(f)[-1].lstrip('.') in extensions
    ]


# extension version
version = get_version()

cmdclass = {
    'build_manpage': BuildManPage,
    #'build_examples': BuildRSTExamplesFromScripts,
}


# PyPI doesn't render markdown yet. Workaround for a sane appearance
# https://github.com/pypa/pypi-legacy/issues/148#issuecomment-227757822
README = op.join(op.dirname(__file__), 'README.md')
try:
    import pypandoc
    long_description = pypandoc.convert(README, 'rst')
except (ImportError, OSError) as exc:
    # attempting to install pandoc via brew on OSX currently hangs and
    # pypandoc imports but throws OSError demanding pandoc
    print(
        "WARNING: pypandoc failed to import or thrown an error while converting"
        " README.md to RST: %r   .md version will be used as is" % exc
    )
    long_description = open(README).read()


setup(
    # basic project properties can be set arbitrarily
    name="datalad_hirni",
    author="CBBS imaging platform developers",
    author_email="michael.hanke@gmail.com",  # TODO establish project email
    version=version,
    description="DataLad extension for CBBS imaging platform workflows",
    long_description=long_description,
    packages=[pkg for pkg in find_packages('.') if pkg.startswith('datalad')],
    # datalad command suite specs from here
    install_requires=[
        'datalad-neuroimaging',
        'datalad-container',
    ],
    extras_require={
        'devel-docs': [
            # used for converting README.md -> .rst for long_description
            'pypandoc',
            # Documentation
            'sphinx',
            'sphinx-rtd-theme',
        ]},
    cmdclass=cmdclass,
    entry_points={
        'datalad.extensions': [
            # the label in front of '=' is the command suite label
            # the entrypoint can point to any symbol of any name, as long it is
            # valid datalad interface specification (see demo in this extensions
            'hirni=datalad_hirni:command_suite',
        ],
        # 'datalad.webapps' is THE entrypoint inspected by the datalad webapp command
        'datalad.webapps': [
            # the label in front of '=' is the webapp name
            # the entrypoint can point to any symbol of any name, as long it is
            # valid datalad interface specification
            'hirni_specedit=datalad_hirni.webapp.specedit.app:SpecEditApp',
        ],
        'datalad.tests': [
            'hirni=datalad_hirni',
        ],
    },
    package_data={
        'datalad_hirni':
            findsome('resources', {'sh'})
    },
)
