Introduction
************

What is datalad-hirni?
======================

Datalad-hirni aims to provide the means to enable automated provenance capturing of a (neuroimaging) study as well as
automated, metadata-driven conversion.
In a way, datalad-hirni is two things. A conceptional idea on how to bind and structure all (raw) data, metadata, code and
computational environments of a study, and a software package to support the consequential workflow to achieve that.
On the software side, datalad-hirni is a Python package and an extension to Datalad_.

.. note::

 Technically, datalad-hirni (and its approach in general) isn't limited to neuroimaging. In a different
 context there's just less convenience provided by the default routines ATM.

.. _datalad: http://datalad.org


Is it free and open source?
===========================

Yes, of course. Feel free to contribute and complain on Github_.

.. _Github: https://github.com/psychoinformatics-de/datalad-hirni

Where do I get it?
==================

As a Python package, you can install datalad-hirni via pip::

  pip install datalad-hirni

What now?
=========

If you want to get a grasp on how it works, you should start :ref:`here <chap_concepts>`.
For diving right into usage have a look at the :ref:`examples <chap_demos>`, especially at the :ref:`study dataset demo <chap_demos_study>` for a start.
