Demo: A Reproducible GLM Analysis
*********************************
:order: 483


This demo shows how to use datalad and datalad-hirni datasets to perform and record reproducible analyses.
We will again use the study dataset as created by the respective `demo <{filename}../datamanagement/study_setup.rst#step-by-step-demo>`_ to provide the raw data.

Prepare the Data for Analysis
-----------------------------

Before analyzing imaging data, we typically have to convert them from their original DICOM format into NIfTI files.
We gain a lot here by adopting the BIDS standard. Up front, it saves us the effort of creating an ad-hoc directory structure. But more importantly, by structuring our data in a standard way (and an increasingly common one), it opens up possibilities for us to easily feed our dataset into existing analysis pipelines and tools.

For the purpose of this demo, we will simply list the commands needed to get a BIDS dataset from the study dataset. For reference: This is the exact same thing we do in the `conversion demo <{filename}../datamanagement/conversion.rst#demo-conversion-to-bids>`_ ::

  % datalad create localizer_scans
  % cd localizer_scans
  % datalad run-procedure cfg_bids
  % datalad install --dataset . --source https://github.com/psychoinformatics-de/hirni-demo sourcedata --recursive
  % datalad hirni-spec2bids --anonymize sourcedata/studyspec.json sourcedata/*/studyspec.json


We should now have a BIDS dataset looking like this::

  % tree -L 2
  .
  ├── dataset_description.json
  ├── participants.tsv -> .git/annex/objects/KF/5x/MD5E-s50--12d3834067b61899d74aad5d48fd5520.tsv/MD5E-s50--12d3834067b61899d74aad5d48fd5520.tsv
  ├── README
  ├── sourcedata
  │   ├── acq1
  │   ├── acq2
  │   ├── code
  │   ├── dataset_description.json
  │   ├── README
  │   └── studyspec.json
  ├── sub-001
  │   ├── anat
  │   ├── func
  │   └── sub-001_scans.tsv -> ../.git/annex/objects/8v/Gj/MD5E-s179--2e78ce543c5bcc8f0b462b7c9b334ad2.tsv/MD5E-s179--2e78ce543c5bcc8f0b462b7c9b334ad2.tsv
  └── task-oneback_bold.json -> .git/annex/objects/3J/JW/MD5E-s1452--62951cfb0b855bbcc3fce91598cbb40b.json/MD5E-s1452--62951cfb0b855bbcc3fce91598cbb40b.json

  % datalad subdatasets -r
  subdataset(ok): sourcedata (dataset)
  subdataset(ok): sourcedata/acq1/dicoms (dataset)
  subdataset(ok): sourcedata/acq2/dicoms (dataset)
  subdataset(ok): sourcedata/code/hirni-toolbox (dataset)
  action summary:
    subdataset (ok: 4)


We are now done with the data preparation. We have the skeleton of a BIDS-compliant dataset that contains all data in the right format and using the correct file names. In addition, the computational environment used to perform the DICOM conversion is tracked, as well as a separate dataset with the input DICOM data. This means we can trace every single file in this dataset back to its origin, including the commands and inputs used to create it.

This dataset is now ready. It can be archived and used as input for one or more analyses of any kind. Let’s leave the dataset directory now::

    % cd ..


A Reproducible GLM Demo Analysis
--------------------------------

With our raw data prepared in BIDS format, we can now conduct an analysis. We will implement a very basic first-level GLM analysis using FSL that runs in just a few minutes. We will follow the same principles that we already applied when we prepared the localizer_scans dataset: the complete capture of all inputs, computational environments, code, and outputs.

Importantly, we will conduct our analysis in a new dataset. The raw localizer_scans dataset is suitable for many different analysis that can all use that dataset as input. In order to avoid wasteful duplication and to improve the modularity of our data structures, we will merely use the localizer_scans dataset as an input, but we will not modify it in any way.
We will simply link it in a new analysis dataset the same way we did during conversion with the raw data::

  % datalad create glm_analysis
  % cd glm_analysis

Following the same logic and commands as before, we will add the localizer_scans dataset as a subdataset of the new glm_analysis dataset to enable comprehensive tracking of all input data within the analysis dataset::

  % datalad install --dataset . --source ../localizer_scans inputs/rawdata

Regarding the layout of this analysis dataset, we unfortunately cannot yet rely on automatic tools and a comprehensive standard (but such guidelines are actively being worked on). However, DataLad nevertheless aids efforts to bring order to the chaos. Anyone can develop their own ideas on how a dataset should be structured and implement these concepts in dataset procedures that can be executed using the datalad run-procedure command.
Here we are going to adopt the YODA principles: a set of simple rules on how to structure analysis dataset. But here, the only relevant aspect is that we want to keep all analysis scripts in the code/ subdirectory of this dataset. We can get a readily configured dataset by running the YODA setup procedure::

  % datalad run-procedure cfg_yoda

Before we can fire up FSL for our GLM analysis, we need two pieces of custom code:

- a small script that can convert BIDS events.tsv files into the EV3 format that FSL can understand, available at https://raw.githubusercontent.com/myyoda/ohbm2018-training/master/section23/scripts/events2ev3.sh
- an FSL analysis configuration template script available at https://raw.githubusercontent.com/myyoda/ohbm2018-training/master/section23/scripts/ffa_design.fsf

Any custom code needs to be tracked if we want to achieve a complete record of how an analysis was conducted. Hence we will store those scripts in our analysis dataset.
We use the `datalad download-url` command to download the scripts and include them in the analysis dataset::

  % datalad download-url --path code/ \
  https://raw.githubusercontent.com/myyoda/ohbm2018-training/master/section23/scripts/events2ev3.sh \
  https://raw.githubusercontent.com/myyoda/ohbm2018-training/master/section23/scripts/ffa_design.fsf

Note, that the commit message shows the URL where each script has been downloaded from::

  % git log

At this point, our analysis dataset contains all of the required inputs. We only have to run our custom code to produce the inputs in the format that FSL expects. First, let’s convert the events.tsv file into EV3 format files.
We use the `datalad run` command to execute the script at code/events2ev3.sh. It requires the name of the output directory (use sub-001) and the location of the BIDS events.tsv file to be converted. The `--input` and `--output` options are used to let DataLad automatically manage these files for you. Important: The subdataset does not actually have the content for the events.tsv file yet. If you use --input correctly, DataLad will obtain the file content for you automatically. Check the output carefully, the script is written in a sloppy way that will produce some output even when things go wrong. Each generated file must have three numbers per line::

  % datalad run -m 'Build FSL EV3 design files' \
    --input inputs/rawdata/sub-001/func/sub-001_task-oneback_run-01_events.tsv \
    --output 'sub-001/onsets' \
    bash code/events2ev3.sh sub-001 {inputs}

Now we’re ready for FSL! And since FSL is certainly not a simple, system program, we will use it in a container and add that container to this analysis dataset. A ready-made container with FSL (~260 MB) is available from shub://ReproNim/ohbm2018-training:fsln.
Use the datalad containers-add command to add this container under the name fsl. Then use the datalad containers-list command to verify that everything worked::

  % datalad containers-add fsl --url shub://ReproNim/ohbm2018-training:fsln
  % datalad containers-list

With this we have completed the analysis setup. At such a milestone it can be useful to label the state of a dataset that can be referred to later on. Let’s add the label ready4analysis here::

  % datalad save --version-tag ready4analysis

All we have left is to configure the desired first-level GLM analysis with FSL. The following command will create a working configuration from the template we stored in `code/`. It uses the arcane, yet powerful sed editor.
We will again use datalad run to invoke our command so that we store in the history how this template was generated (so that we may audit, alter, or regenerate this file in the future — fearlessly)::

  % datalad run \
  -m "FSL FEAT analysis config script" \
  --output sub-001/1stlvl_design.fsf \
  bash -c 'sed -e "s,##BASEPATH##,{pwd},g" -e "s,##SUB##,sub-001,g" \
  code/ffa_design.fsf > {outputs}'

The command that we will run now in order to compute the analysis results is a simple feat sub-001/1stlvl_design.fsf. However, in order to achieve the most reproducible and most portable execution, we should tell the `datalad containers-run` command what the inputs and outputs are. DataLad will then be able to obtain the required NIfTI time series file from the localizer_scans raw subdataset.
The following command takes around 5 minutes to complete on an average system::

  % datalad containers-run --container-name fsl -m "sub-001 1st-level GLM" \
  --input sub-001/1stlvl_design.fsf \
  --input sub-001/onsets \
  --input inputs/rawdata/sub-001/func/sub-001_task-oneback_run-01_bold.nii.gz \
  --output sub-001/1stlvl_glm.feat \
  fsl5.0-feat '{inputs[0]}'

Once this command finishes, DataLad will have captured the entire FSL output, and the dataset will contain a complete record all the way from the input BIDS dataset to the GLM results (which, by the way, performed an FFA localization on a real BOLD imaging dataset, take a look!). The BIDS subdataset in turn has a complete record of all processing down from the raw DICOMs onwards.


Get Ready for the Afterlife
---------------------------

Once a study is complete and published it is important to archive data and results, for example, to be able to respond to inquiries from readers of an associated publication. The modularity of the study units makes this straightforward and avoid needless duplication. We now that the raw data for this GLM analysis is tracked in its own dataset (localizer_scans) that only needs to be archived once, regardless of how many analyses use it as input. This means that we can “throw away” this subdataset copy within this analysis dataset. DataLad can re-obtain the correct version at any point in the future, as long as the recorded location remains accessible.
We can use the `datalad diff` command and `git log` to verify that the subdataset is in the same state as when it was initially added. Then use datalad uninstall to delete it::

  % datalad diff -- inputs/rawdata
  % git log -- inputs/rawdata
  % datalad uninstall --dataset . inputs/rawdata --recursive

Before we archive these analysis results, we can go one step further and verify their computational reproducibility. DataLad provides a rerun command that is capable of “replaying” any recorded command. The following command we re-execute the FSL analysis (the command that was recorded since we tagged the dataset as “ready4analysis”). It will record the recomputed results in a separate Git branch named “verify” of the dataset. We can then automatically compare these new results to the original ones in the “master” branch. We will see that all outputs can be reproduced in bit-identical form. The only changes are observed in log files that contain volatile information, such as time steps::

  # rerun FSL analysis from scratch (~5 min)
  % datalad rerun --branch verify --onto ready4analysis --since ready4analysis
  % # check that we are now on the new `verify` branch
  % git branch
  % # compare which files have changes with respect to the original results
  % git diff master --stat
  % # switch back to the master branch and remove the `verify` branch
  % git checkout master
  % git branch -D verify

So, hopefully we've shown that:

- we can implement a complete imaging study using DataLad datasets to represent units of data processing
- each unit comprehensively captures all inputs and data processing leading up to it
- this comprehensive capture facilitates re-use of units, and enables computational reproducibility
- carefully validated intermediate results (captured as a DataLad dataset) are a candidate for publication with minimal additional effort
