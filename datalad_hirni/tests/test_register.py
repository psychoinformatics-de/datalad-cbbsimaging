from datalad.tests.utils import assert_result_count


def test_register():
    import datalad.api as da
    assert hasattr(da, 'hirni_spec4anything')
    assert hasattr(da, 'hirni_dicom2spec')
    assert hasattr(da, 'hirni_import_dcm')
    assert hasattr(da, 'hirni_spec2bids')

