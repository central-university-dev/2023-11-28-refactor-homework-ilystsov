import os
from libcst import MetadataWrapper

from refactoring_tool.mover import (
    create_module_attribute,
    DefinitionExtractor,
    DefinitionInserter,
    ImportUpdater,
    Mover,
)
import libcst as cst
import pytest
import refactoring_tool.mover
from refactoring_tool.renamer import get_full_module_name


@pytest.fixture
def dummy_definition():
    return """
class _:
    ...
    """



def remove_empty_lines(code: str) -> str:
    return "\n".join(line for line in code.splitlines() if line.strip())


def test_create_module_attribute_with_full_name():
    # Тест с полным именем модуля
    module_name = "a.b.c"
    result = create_module_attribute(module_name)
    assert isinstance(result, cst.Attribute)
    assert result.value.value == "a"
    assert result.attr.value.value == "b"
    assert result.attr.attr.value == "c"


def test_create_module_attribute_with_single_name():
    # Тест с одночастным именем модуля
    module_name = "a"
    result = create_module_attribute(module_name)
    assert isinstance(result, cst.Name)
    assert result.value == "a"


def test_create_module_attribute_with_empty_name():
    # Тест с пустым именем модуля
    module_name = ""
    with pytest.raises(ValueError):
        create_module_attribute(module_name)


def test_definition_extractor_leave_FunctionDef():
    source_code = """
def some_function():
    pass

def another_function():
    pass
"""
    wrapper = MetadataWrapper(cst.parse_module(source_code))
    extractor = DefinitionExtractor(name_to_move="some_function", new_module_name="new_module")
    res_tree = wrapper.visit(extractor)
    assert "def some_function():\n    pass" not in res_tree.code
    assert extractor.def_start is not None
    assert extractor.def_end is not None
    source_lines = source_code.splitlines()
    function_start_line = source_lines[extractor.def_start - 1].strip()
    function_end_line = source_lines[extractor.def_end - 1].strip()
    assert function_start_line == "def some_function():"
    assert function_end_line == "pass"


def test_definition_extractor_leave_ClassDef():
    source_code = """
class SomeClass:
    x = 0
    y = 0

class AnotherClass:
    ...
"""
    wrapper = MetadataWrapper(cst.parse_module(source_code))
    extractor = DefinitionExtractor(name_to_move="SomeClass", new_module_name="new_module")

    res_tree = wrapper.visit(extractor)

    assert "class SomeClass:\n    x = 0\n    y = 0" not in res_tree.code
    assert extractor.def_start is not None
    assert extractor.def_end is not None

    source_lines = source_code.splitlines()
    function_start_line = source_lines[extractor.def_start - 1].strip()
    function_end_line = source_lines[extractor.def_end - 1].strip()

    assert function_start_line == "class SomeClass:"
    assert function_end_line == "y = 0"


def test_definition_extractor_leave_Module():
    source_code = """
import os
from libcst.metadata import PositionProvider
import sys

def some_function():
    pass

def another_function():
    pass
"""
    wrapper = MetadataWrapper(cst.parse_module(source_code))
    extractor = DefinitionExtractor(name_to_move="some_function", new_module_name="new.module")

    extractor.def_start = 4
    extractor.def_end = 5

    updated_tree = wrapper.visit(extractor)

    assert "from new.module import some_function" in updated_tree.code
    assert updated_tree.code.count("from new.module import some_function") == 1
    print(updated_tree.code)
    import_lines = [
        line.strip()
        for line in updated_tree.code.splitlines()
        if line.strip().startswith("import") or line.strip().startswith("from")
    ]
    assert import_lines[-1] == "from new.module import some_function"


def test_definition_inserter_leave_Module():
    source_code = """
import os
import sys

def existing_function():
    pass
"""
    updated_code = """
import os
import sys

class NewClass:
    pass

def existing_function():
    pass
"""
    inserter = DefinitionInserter(
        definition="class NewClass:\n    pass", moved_name="NewClass", old_module_name="old.module"
    )
    tree = cst.parse_module(source_code)
    updated_tree = tree.visit(inserter)
    assert remove_empty_lines(updated_tree.code) == remove_empty_lines(updated_code)

    second_pass_tree = updated_tree.visit(inserter)
    assert remove_empty_lines(second_pass_tree.code) == remove_empty_lines(updated_code)


def test_definition_inserter_leave_ImportFrom(dummy_definition):
    source_imports = """
from old.module import MovedClass, AnotherClass
"""
    updated_imports = """
from old.module import AnotherClass
"""

    inserter = DefinitionInserter(definition=dummy_definition, moved_name="MovedClass", old_module_name="old.module")
    tree = cst.parse_module(source_imports)
    updated_tree = tree.visit(inserter)
    assert updated_tree.code.strip().splitlines()[0] == updated_imports.strip()

    inserter.alias_name = None
    source_imports_with_alias = """
from old.module import MovedClass as mc, AnotherClass
"""
    updated_imports_with_alias = """
from old.module import AnotherClass
"""
    tree_with_alias = cst.parse_module(source_imports_with_alias)
    updated_tree_with_alias = tree_with_alias.visit(inserter)
    assert updated_tree_with_alias.code.strip() == updated_imports_with_alias.strip()
    assert inserter.alias_name == "mc"

    source_imports_empty_import = """
from old.module import MovedClass
"""
    tree_empty_import = cst.parse_module(source_imports_empty_import)
    updated_tree_empty_import = tree_empty_import.visit(inserter)
    assert not updated_tree_empty_import.body


def test_definition_inserter_leave_Name(dummy_definition):
    source_code = """
from old.module import SomeClass as sm
sm()
print(sm)
"""
    expected_code = """
class _:
    ...
SomeClass()
print(SomeClass)
"""

    inserter = DefinitionInserter(definition=dummy_definition, moved_name="SomeClass", old_module_name="old.module")
    tree = cst.parse_module(source_code)
    updated_tree = tree.visit(inserter)
    assert remove_empty_lines(updated_tree.code) == remove_empty_lines(expected_code)


def test_definition_inserted_leave_Attribute(dummy_definition):
    source_code = """
import old_module
old_module.SomeClass.some_method()
    """

    inserter = DefinitionInserter(definition=dummy_definition, moved_name="SomeClass", old_module_name="old_module")
    tree = cst.parse_module(source_code)
    updated_tree = tree.visit(inserter)
    lines = updated_tree.code.strip().splitlines()
    first_line, last_line = lines[0], lines[-1]
    assert first_line == "import old_module"
    assert last_line == "SomeClass.some_method()"


def test_imported_updater_process_import_from():
    source_code = """
from old.module import MovedClass, AnotherClass
"""
    expected_code = """
from old.module import AnotherClass
from new.module import MovedClass
"""
    tree = cst.parse_module(source_code)
    updater = ImportUpdater("MovedClass", "old.module", "new.module")
    new_body, new_import_added = updater.process_import_from(tree.body[0].body[0], tree.body[0], [], False)

    updated_body = [
        stmt if isinstance(stmt, cst.SimpleStatementLine) else cst.SimpleStatementLine(body=[stmt]) for stmt in new_body
    ]

    updated_tree = tree.with_changes(body=updated_body)
    assert remove_empty_lines(updated_tree.code) == remove_empty_lines(expected_code)


def test_import_updater_process_import():
    source_code = """
import old.module
"""
    expected_code = """
import new.module
import old.module
"""
    tree = cst.parse_module(source_code)
    updater = ImportUpdater("MovedClass", "old.module", "new.module")
    new_body, new_import_added = updater.process_import(tree.body[0].body[0], tree.body[0], [], False)

    updated_body = [
        stmt if isinstance(stmt, cst.SimpleStatementLine) else cst.SimpleStatementLine(body=[stmt]) for stmt in new_body
    ]

    updated_tree = tree.with_changes(body=updated_body)

    assert remove_empty_lines(updated_tree.code) == remove_empty_lines(expected_code)


def test_import_updater_leave_Module():
    source_code = """
import old.module
from old.module import MovedClass, AnotherClass
from another.module import DifferentClass
"""
    expected_code = """
import new.module
import old.module
from old.module import AnotherClass
from another.module import DifferentClass
"""
    tree = cst.parse_module(source_code)
    updater = ImportUpdater("MovedClass", "old.module", "new.module")
    updated_tree = tree.visit(updater)

    assert remove_empty_lines(updated_tree.code) == remove_empty_lines(expected_code)


def test_import_updater_leave_attribute():
    source_code = """
import old.module
old.module.MovedClass.method()
"""
    expected_code = """
import new.module
import old.module
new.module.MovedClass.method()
"""
    tree = cst.parse_module(source_code)
    updater = ImportUpdater("MovedClass", "old.module", "new.module")
    updated_tree = tree.visit(updater)

    assert remove_empty_lines(updated_tree.code) == remove_empty_lines(expected_code)


def file_content(file_path):
    with open(file_path, "r") as file:
        return file.read()


def test_mover_move_test1():
    src_folder = "tests/fixtures/mover_test1"
    dest_folder = "tests/fixtures/mover_test1_expected"
    project_root = "tests/fixtures/mover_test1"

    src_file_path = os.path.join(src_folder, "file1.py")
    dest_file_path = os.path.join(src_folder, "file2.py")

    mover = Mover(
        project_root=project_root,
        src_file_path=src_file_path,
        dest_file_path=dest_file_path,
        class_or_func_name="SomeClass",
    )
    mover.move()

    assert file_content(os.path.join(src_folder, "file1.py")) == file_content(os.path.join(dest_folder, "file1.py"))
    assert file_content(os.path.join(src_folder, "file2.py")) == file_content(os.path.join(dest_folder, "file2.py"))
    assert file_content(os.path.join(src_folder, "file3.py")) == file_content(os.path.join(dest_folder, "file3.py"))


def test_mover_move_method_test2():
    src_folder = "tests/fixtures/mover_test2"
    dest_folder = "tests/fixtures/mover_test2_expected"
    project_root = "tests/fixtures/mover_test2"

    src_file_path = os.path.join(src_folder, "dir/subdir/file1.py")
    dest_file_path = os.path.join(src_folder, "file3.py")

    mover = Mover(
        project_root=project_root,
        src_file_path=src_file_path,
        dest_file_path=dest_file_path,
        class_or_func_name="SomeClass",
    )
    mover.move()

    assert file_content(os.path.join(src_folder, "dir/subdir/file1.py")) == file_content(
        os.path.join(dest_folder, "dir/subdir/file1.py")
    )
    assert file_content(os.path.join(src_folder, "dir/file2.py")) == file_content(
        os.path.join(dest_folder, "dir/file2.py")
    )
    assert file_content(os.path.join(src_folder, "file3.py")) == file_content(os.path.join(dest_folder, "file3.py"))

