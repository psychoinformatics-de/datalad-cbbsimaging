.. _chap_demos_conversion:

Demo: Conversion to BIDS
------------------------


This demo shows how to convert a hirni study dataset into a BIDS compliant dataset.
The study dataset we use is the one created by the :ref:`study dataset demo <chap_demos_study>`.
We will use a published version of that dataset available from GitHub, but you can also build it yourself by following said demo and use that one.


BIDS Dataset
~~~~~~~~~~~~

The idea is to create a new dataset, that will become the BIDS Dataset and reference our study dataset - that bundles all the raw data - by making it a subdataset of the derived one.
Please note, that this does NOT mean, that the new BIDS dataset contains the raw data. It just references it and thereby creates a fully reproducible history record of how it came to be.
The study dataset does NOT need to be shared if you want to share the BIDS dataset. Rather it is possible to trace everything back to the original raw data for everyone who has the BIDS dataset IF he also has access/permission to get that subdataset.

In order to get our to-be BIDS dataset from the raw dataset, we create a new dataset and run the `cfg_bids` procedure to configure it::

  % datalad create demo_bids
  % cd demo_bids
  % datalad run-procedure cfg_bids

Now we install our study dataset as a subdataset into our new dataset at its subdirectory `sourcedata`. By that, we reference the exact state of our study dataset at the moment of installation.
While this may create some data duplication, please note several things: First, the new subdataset doesn't need to hold all of the actual content of the study dataset's files (although it can retrieve it, it doesn't by default during installation). Rather it's about referencing the input data (including the code and environments in hirni's toolbox) at their exact version to achieve full reproducibility. We can thereby track the converted data back to the raw data and the exact conversion routine that brought it into existence.
Second, this subdataset can later be removed by `datalad uninstall`, freeing the space on the filesystem while keeping the reference::

  % datalad install --dataset . --source https://github.com/psychoinformatics-de/hirni-demo sourcedata --recursive

Note, that if you want to use a local study dataset (i.e. created yourself via the study dataset demo) you can simply replace that URL with the path to your local one.


The actual conversion is based on the specification files in the study dataset. You can convert a single one of them (meaning: Everything such a file specifies) or an arbitrary number, including everything at once, of course.
Lets first convert the study level specification and second all the acquisitions by the following call::

  % datalad hirni-spec2bids --anonymize sourcedata/studyspec.json sourcedata/*/studyspec.json

The `anonymize` switch will cause the command to use the anonymized subject identifiers and encode all records of where exactly the data came from into hidden sidecar files, that can then be excluded from publishing/sharing this dataset.

`datalad hirni-spec2bids` will run datalad procedures on the raw data as specified in the specification files (remember for example that we set a procedure "copy-converter" for our events.tsv file). Those procedures are customizable. The defaults we are using here, come from hirni's toolbox dataset. The default procedure to convert the DICOM files uses a containerized converter. It will NOT use, what you happen to have locally, but this defined and in the datasets referenced environment to do the conversion.
This requires a download of that container (happens automatically) and enables the reproducibility of this routine, since the exact environment the conversion was ran in will be recorded in the dataset's history.
In addition, this will cause datalad to retrieve the actual data of the study subdataset in `sourcedata`. Remember that you can `datalad uninstall` that subdataset after conversion or use `datalad drop` to throw away its copy of particular files.
If you use the BIDS-Validator (https://bids-standard.github.io/bids-validator/) to check the resulting dataset, there should be an error message, though. This is because our events.tsv file references stimuli files, we don't actually have available to add to the dataset.
For the purpose of this demo, this should be fine.

Other than that, we have a valid BIDS dataset now, that can be used with BIDS-Apps or any kind of software that is able to deal with this standard. Since we have the raw data in a subdataset, we can aggregate DICOM metadata from it into the BIDS dataset, which would be available even when the study dataset was uninstalled from the BIDS dataset. If we keep using `datalad-run` / `datalad containers-run` for any processing to follow (as hirni internally does), we are able to trace back the genesis and evolution of each file to the raw data, the exact code and the environments it ran in to alter this file or bring it into its existence.
