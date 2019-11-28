.. _chap_customization:

Customization
*************

There are a lot of ways to customize datalad-hirni. Some things are just a matter of configuration settings, while
others involve a few lines of (Python) code.

Configuration
=============

As a DataLad extension, datalad-hirni uses DataLad's
`config mechanism <https://datalad.readthedocs.io/en/latest/config.html>`_. It just adds some additional variables. If
you look for a possible configuration to change some specific behaviour of the commands, refer also to the help pages
for those commands. Please don't hesitate to file an issue on
`GitHub <https://github.com/psychoinformatics-de/datalad-hirni>`_ if there's something you would like become
configurable as well.

**datalad.hirni.toolbox.url**
    This can be used to overwrite the default url to get the toolbox from. The url is then respected by the ``cfg_hirni``
    procedure. Please note, that therefore it will have no effect, if the toolbox was already installed into your
    dataset.

    This configuration may be used to refer to an offline version of hirni's toolbox or to switch to another toolbox
    dataset altogether.

**datalad.hirni.studyspec.filename**
    Use this configuration to change the default name for specification files (``studyspec.json``).

**datalad.hirni.dicom2spec.rules**
    Set this to point to a Python file defining rules for how to derive a specification from DICOM metadata. (See below
    for more on implementing such rules). This configuration can be set multiple times, which will result in those rules
    overwriting each other. Therefore the order in which they are specified matters, with the later rules overwriting
    earlier ones. As with any DataLad configuration in general, the order of sources would be *system*, *global*,
    *local*, *dataset*. This could be used for having institution-wide rules via the system level, a scanner-based rule
    at the global level (of a specific computer at the scanner site), user-based and study-specific rules, each of which
    could either go with what the previous level decided or overwrite it.

**datalad.hirni.import.acquisition-format**
    This setting allows to specify a Python format string, that will be used by ``datalad hirni-import-dcm`` if no
    acquisition name was given. It defines the name to be used for an acquisition (the directory name) based on DICOM
    metadata. The default value is ``{PatientID}``. Something that is enclosed with curly brackets will be replaced by
    the value of a variable with that name everything else is taken literally. Every field of the DICOM headers is
    available as such a variable. You could also combine several like ``{PatientID}_{PatientName}``.


Procedures
==========

DataLad `procedures <https://datalad.readthedocs.io/en/latest/generated/man/datalad-run-procedure.html>`_ are used in
different places with datalad-hirni. Wherever this is the case you can use your own procedure instead (or in addition).
Most notably procedures are the drivers of the conversion and therefore the pieces used to plugin arbitrary conversion
routines (in fact, the purpose of a procedure is up to you - for example, one can use the conversion specification and
those procedures for preprocessing as well). The following is an outlining of how this works.

A specification snippet defines a list of procedures and how exactly they are called. Any DataLad procedure can be
referenced therein, it is, however, strongly recommended to include them in the dataset they are supposed to run on or
possibly in a subdataset thereof (as is the case with the toolbox). For full reproducibility you want to avoid
referencing a procedure, that is not tracked by the dataset or any of its subdataset. Sooner or later this would be
doomed to become a reference to nowhere.

Those procedures are then executed by ``datalad hirni-spec2bids`` in the order they are appearing in that list. A single
entry in that list is a dictionary, specifying the name of the procedure and optionally a format string to use for
calling it and, also optionally, a flag indicating whether it should be executed only, if ``datalad hirni-spec2bids``
was called with ``--anonymize``.

For example (taken from the `demo dataset <https://github.com/psychoinformatics-de/hirni-demo/>`_, acquisition2)
(a part of) the snippet of the specification for the DICOM image series and another one specifying the use of the
"copy converter" for an ``events.tsv`` file. (See the :ref:`study dataset demo <chap_demos_study>` for context)::


    {"location":"dicoms",
     "dataset-id":"7cef7b58-400d-11e9-a522-e8b1fc668b5e",
     "dataset-refcommit":"2f98e53c171d410c4b54851f86966934b78fc870",
     "type":"dicomseries:all"
     "id":{"approved":false,
           "value":401},
     "description":{"approved":false,
                    "value":"func_task-oneback_run-1"},
     "anon-subject":{"approved":false,
                     "value":"001"},
     "subject":{"approved":false,
                "value":"02"},
     "bids-modality":{"approved":false,
                      "value":"bold"},
     "bids-run":{"approved":false,
                 "value":"01"},
     "bids-session":{"approved":false,
                     "value":null},
     "bids-task":{"approved":false,
                  "value":"oneback"},
     "procedures":[
        {"procedure-name":{"approved":false,
                           "value":"hirni-dicom-converter"}
         "procedure-call":{"approved":false,
                           "value":null},}
         "on-anonymize":{"approved":false,
                         "value":false}
         }
      ]
    }

    {"location":"events.tsv",
     "dataset-id":"3f27c348-400d-11e9-a522-e8b1fc668b5e",
     "dataset-refcommit":"4cde2dc1595a1f3ba694f447dbb0a1b1ec99d69c",
     "type":"events_file",
     "id":{"approved":false,"value":401},
     "description":{"approved":false,"value":"func_task-oneback_run-1"},
     "anon-subject":{"approved":false,"value":"001"},
     "subject":{"approved":false,"value":"02"}
     "bids-modality":{"approved":false,"value":"bold"},
     "bids-run":{"approved":false,"value":"01"},
     "bids-session":{"approved":false,"value":null},
     "bids-task":{"approved":false,"value":"oneback"},
     "procedures":[
        {"procedure-name":{"approved":true,
                           "value":"copy-converter"},
         "procedure-call":{"approved":true,
                           "value":"bash {script} {{location}} {ds}/sub-{{bids-subject}}/func/sub-{{bids-subject}}_task-{{bids-task}}_run-{{bids-run}}_events.tsv"}
         }
      ]
    }


Such format strings to define the call can use replacements (TODO: refer to datalad-run/datalad-run-procedure) by
enclosing valid variables with curly brackets, which is then replaced by the values of those variables when this is
executed. For procedures referenced in the specification snippets and executed by ``datalad hirni-spec2bids`` all fields
of the currently processed specification snippets are available for that way of passing them to the procedures. That way
any conversion routine you might want to make (likely wrap into) such a procedure can be made aware of all the metadata
recorded in the respective snippet.
The format strings to define how exactly a particular procedure should be called, can be provided by the procedure
itself, if that procedure is registered in a dataset. This is treated as a default and can be overwritten by the
specification. If the default is sufficiently generic, the ``call-format`` field in the specification can remain empty.
The only specification field actually mandatory for a procedure is ``procedure-name``, of course.


*TODO*
    have an actual step-by-step example implementation of a (conversion) procedure


Rules
=====

The rule system to derive a specification for DICOM image series from the DICOM metadata consists of two parts. One is a
configuration determining which existing rule(s) to use and the other is providing such rules that then can be
configured to be the one to be used.

*TODO*
    config vs. implementation

*TODO*
    - Say a thing or two about those:
    - https://github.com/psychoinformatics-de/datalad-hirni/blob/master/datalad_hirni/resources/rules/custom_rules_template.py
    - https://github.com/psychoinformatics-de/datalad-hirni/blob/master/datalad_hirni/resources/rules/test_rules.py
    - likely walk through a reasonably small example implementation