from dfsync.filters import USER_FILTERS, PythonBlackFilter, PythonSyntaxFilter


def test_rejects_python_that_does_not_parse(tmp_path):
    src = tmp_path / "broken.py"
    src.write_text("def f(:\n")
    assert PythonSyntaxFilter().is_filtered(src_file_path=str(src))


def test_syncs_valid_python_even_if_not_formatted(tmp_path):
    src = tmp_path / "ugly.py"
    src.write_text("x  =  [1,\n2]\n")
    assert not PythonSyntaxFilter().is_filtered(src_file_path=str(src))


def test_ignores_files_that_are_not_python(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("def f(:\n")
    assert not PythonSyntaxFilter().is_filtered(src_file_path=str(src))


def test_syncs_a_deleted_file(tmp_path):
    assert not PythonSyntaxFilter().is_filtered(src_file_path=str(tmp_path / "gone.py"))


def test_old_name_still_works():
    assert PythonBlackFilter is PythonSyntaxFilter
    assert any(isinstance(f, PythonSyntaxFilter) for f in USER_FILTERS)
