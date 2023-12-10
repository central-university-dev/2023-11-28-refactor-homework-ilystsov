import os

import libcst as cst
import pytest

from refactoring_tool.renamer import get_full_module_name, resolve_relative_import, RenameTransformer, \
    ImportRenameTransformer, Renamer
from tests.test_mover import file_content

@pytest.fixture
def transformer():
    return ImportRenameTransformer(
        module_name="some_module",
        old_name="old_name",
        new_name="new_name",
        file_path="dummy/path.py"
    )


@pytest.mark.parametrize("module_name, expected", [
    ("module", "module"),
    ("parent.child.module", "parent.child.module"),
    ("parent.module", "parent.module"),
])
def test_get_full_module_name(module_name, expected):
    module_node = cst.parse_expression(module_name)
    assert get_full_module_name(module_node) == expected


@pytest.mark.parametrize("import_path, file_path, expected", [
    (".module", "/project/dir/file.py", ".project.module"),
    ("..module", "/project/dir/subdir/file.py", ".project.module"),
    (".module", "/project/file.py", ".module"),
])
def test_resolve_relative_import(import_path, file_path, expected):
    assert resolve_relative_import(import_path, file_path) == expected


def test_rename_transformer_leave_name():
    source_code = "old_name = 5"
    tree = cst.parse_module(source_code)

    transformer = RenameTransformer(old_name="old_name", new_name="new_name")
    wrapper = cst.metadata.MetadataWrapper(tree)
    updated_tree = wrapper.visit(transformer)

    assert updated_tree.code == "new_name = 5"


def test_rename_transformer_leave_import_from():
    source_code = "from some_module import old_name as old_name_alias\ntype(old_name_alias)"
    tree = cst.parse_module(source_code)

    transformer = RenameTransformer(old_name="old_name_alias", new_name="new_name_alias")
    wrapper = cst.metadata.MetadataWrapper(tree)
    updated_tree = wrapper.visit(transformer)

    assert updated_tree.code == "from some_module import old_name as new_name_alias\ntype(new_name_alias)"


def test_import_rename_transformer_leave_import_from(transformer):
    source_code = "from some_module import old_name, other_name"
    wrapper = cst.metadata.MetadataWrapper(cst.parse_module(source_code))
    updated_tree = wrapper.visit(transformer)

    assert updated_tree.code == "from some_module import new_name, other_name"


def test_import_rename_transformer_leave_attribute(transformer):
    source_code = """
from some_module import old_name
a = old_name.attribute
"""
    wrapper = cst.metadata.MetadataWrapper(cst.parse_module(source_code))
    updated_tree = wrapper.visit(transformer)

    assert updated_tree.code == """
from some_module import new_name
a = new_name.attribute
"""


def test_import_rename_transformer_leave_name(transformer):
    source_code = """
import some_module
a = some_module.old_name
"""
    wrapper = cst.metadata.MetadataWrapper(cst.parse_module(source_code))
    updated_tree = wrapper.visit(transformer)

    assert updated_tree.code == """
import some_module
a = some_module.new_name
"""


def test_renamer_rename_test1():
    src_folder = "tests/fixtures/renamer_test1"
    dest_folder = "tests/fixtures/renamer_test1_expected"
    project_root = "tests/fixtures/renamer_test1"

    file_path = os.path.join(src_folder, "file1.py")

    renamer = Renamer(
        project_root=project_root,
        file_path=file_path,
        old_name="SomeClass",
        new_name="NEW_CLASS",
    )
    renamer.rename()

    assert file_content(os.path.join(src_folder, "file1.py")) == file_content(os.path.join(dest_folder, "file1.py"))


