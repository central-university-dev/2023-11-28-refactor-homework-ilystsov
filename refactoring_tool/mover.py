import libcst as cst
from libcst.metadata import PositionProvider, QualifiedNameProvider
import os
from refactoring_tool.renamer import get_full_module_name


def create_module_attribute(module_name: str) -> cst.Attribute:
    parts = [part for part in module_name.split(".") if part]
    if not parts:
        raise ValueError("Module name cannot be empty or only dots!")
    module_attr = cst.Name(parts[-1])
    for part in reversed(parts[:-1]):
        module_attr = cst.Attribute(value=cst.Name(part), attr=module_attr)
    return module_attr


class DefinitionExtractor(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, name_to_move: str, new_module_name: str) -> None:
        self.name_to_move = name_to_move
        self.def_start: int | None = None
        self.def_end: int | None = None
        self.new_module_name = new_module_name

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.RemovalSentinel | cst.ClassDef:
        if original_node.name.value == self.name_to_move:
            positions = self.get_metadata(PositionProvider, original_node)
            self.def_start = positions.start.line
            self.def_end = positions.end.line
            return cst.RemoveFromParent()
        return updated_node

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.RemovalSentinel | cst.FunctionDef:
        if original_node.name.value == self.name_to_move:
            positions = self.get_metadata(PositionProvider, original_node)
            self.def_start = positions.start.line
            self.def_end = positions.end.line
            return cst.RemoveFromParent()
        return updated_node

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        if self.def_start is not None and self.def_end is not None:
            insert_position = 0
            new_body = list(updated_node.body)
            for position, element in enumerate(new_body):
                if isinstance(element, cst.SimpleStatementLine) and any(
                    isinstance(body_el, (cst.ImportFrom, cst.Import)) for body_el in element.body
                ):
                    insert_position = position + 1

            new_import = cst.ImportFrom(
                module=create_module_attribute(self.new_module_name),
                names=[cst.ImportAlias(name=cst.Name(value=self.name_to_move))],
            )

            new_body.insert(insert_position, new_import)
            new_body.insert(insert_position + 1, cst.EmptyLine())
            return updated_node.with_changes(body=new_body)
        return updated_node


class DefinitionInserter(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)

    def __init__(self, definition: str, moved_name: str, old_module_name: str) -> None:
        self.definition = definition
        self.moved_name = moved_name
        self.old_module_name = old_module_name
        self.inserted_flag: bool = False
        self.alias_name: str | None = None

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        if not self.inserted_flag:
            insert_position = 0
            new_body = list(updated_node.body)
            for i, element in enumerate(new_body):
                if isinstance(element, cst.SimpleStatementLine) and any(
                    isinstance(s, (cst.ImportFrom, cst.Import)) for s in element.body
                ):
                    insert_position = i + 1
            parsed_definition = cst.parse_statement(self.definition + "\n")
            new_body.insert(insert_position, cst.EmptyLine())
            new_body.insert(insert_position + 1, parsed_definition)
            new_body.insert(insert_position + 2, cst.EmptyLine())
            self.inserted_flag = True
            return updated_node.with_changes(body=new_body)
        return updated_node

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom | cst.RemovalSentinel:
        if original_node.module and get_full_module_name(original_node.module) == self.old_module_name:
            for alias in original_node.names:
                if alias.name.value == self.moved_name:
                    if alias.asname:
                        self.alias_name = alias.asname.name.value
                    break
            rest_names = [alias for alias in original_node.names if alias.name.value != self.moved_name]
            if rest_names:
                return updated_node.with_changes(names=rest_names)
            else:
                return cst.RemoveFromParent()
        return updated_node

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        if original_node.value == self.alias_name:
            return cst.Name(value=self.moved_name)
        return updated_node

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.Attribute | cst.Name:
        full_module_name = get_full_module_name(original_node.value)
        if full_module_name == self.old_module_name and original_node.attr.value == self.moved_name:
            return cst.Name(value=self.moved_name)
        return updated_node


class ImportUpdater(cst.CSTTransformer):
    def __init__(self, moved_name: str, old_module_name: str, new_module_name: str) -> None:
        self.moved_name = moved_name
        self.old_module_name = old_module_name
        self.new_module_name = new_module_name

    def process_import_from(self, item, statement, new_body, new_import_added):
        if item.module and get_full_module_name(item.module) == self.old_module_name:
            rest_names = []
            as_name = None
            for alias in item.names:
                if alias.name.value == self.moved_name:
                    as_name = alias.asname
                else:
                    rest_names.append(alias)
            if rest_names:
                new_body.append(statement.with_changes(body=[item.with_changes(names=rest_names)]))
            if self.moved_name in {alias.name.value for alias in item.names} and not new_import_added:
                new_alias = cst.ImportAlias(name=cst.Name(value=self.moved_name), asname=as_name)
                new_import = cst.ImportFrom(module=create_module_attribute(self.new_module_name), names=[new_alias])
                new_import_statement = cst.SimpleStatementLine(body=[new_import])
                new_body.append(new_import_statement)
                new_import_added = True
        else:
            new_body.append(statement)
        return new_body, new_import_added

    def process_import(self, item, statement, new_body, new_import_added):
        if any(self.old_module_name == get_full_module_name(alias.name) for alias in item.names):
            if not new_import_added:
                if "." in self.new_module_name:
                    new_module = create_module_attribute(self.new_module_name)
                else:
                    new_module = cst.Name(value=self.new_module_name)

                new_import = cst.Import(names=[cst.ImportAlias(name=new_module)])
                new_import_statement = cst.SimpleStatementLine(body=[new_import])
                new_body.append(new_import_statement)
                new_import_added = True
            new_names = [alias for alias in item.names]
            new_body.append(statement.with_changes(body=[item.with_changes(names=new_names)]))
        else:
            new_body.append(statement)
        return new_body, new_import_added

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        new_body = []
        new_import_added = False
        for statement in updated_node.body:
            if not isinstance(statement, cst.SimpleStatementLine):
                new_body.append(statement)
                continue
            for item in statement.body:
                if isinstance(item, cst.ImportFrom):
                    new_body, new_import_added = self.process_import_from(item, statement, new_body, new_import_added)
                elif isinstance(item, cst.Import):
                    new_body, new_import_added = self.process_import(item, statement, new_body, new_import_added)
                else:
                    new_body.append(statement)
        return updated_node.with_changes(body=new_body)

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.Attribute:
        if isinstance(original_node.value, cst.Attribute) or isinstance(original_node.value, cst.Name):
            full_module_name = get_full_module_name(original_node.value)
            if full_module_name == self.old_module_name and original_node.attr.value == self.moved_name:
                if "." in self.new_module_name:
                    new_module_attr = create_module_attribute(self.new_module_name)
                    return updated_node.with_changes(value=new_module_attr, attr=cst.Name(value=self.moved_name))
                else:
                    return updated_node.with_changes(
                        value=cst.Name(value=self.new_module_name), attr=cst.Name(value=self.moved_name)
                    )
        return updated_node


class Mover:
    def __init__(self, project_root, src_file_path, dest_file_path, class_or_func_name):
        self.src_file_path = src_file_path
        self.dest_file_path = dest_file_path
        self.class_or_func_name = class_or_func_name
        self.project_root = project_root
        self.relative_src_path = (
            os.path.relpath(self.src_file_path, self.project_root).rstrip(".py").replace(os.path.sep, ".")
        )
        self.relative_dest_path = (
            os.path.relpath(self.dest_file_path, self.project_root).rstrip(".py").replace(os.path.sep, ".")
        )

    def move(self) -> None:
        with open(self.src_file_path, "r") as file:
            src_code = file.read()

        extractor = DefinitionExtractor(self.class_or_func_name, self.relative_dest_path)
        wrapper = cst.metadata.MetadataWrapper(cst.parse_module(src_code))
        src_tree = wrapper.visit(extractor)

        if extractor.def_start is None or extractor.def_end is None:
            print("Search for definition failed!")
            return

        with open(self.src_file_path, "w") as file:
            file.write(src_tree.code)

        try:
            with open(self.dest_file_path, "r") as file:
                dest_code = file.read()
        except FileNotFoundError:
            dest_code = ""

        inserter = DefinitionInserter(
            "\n".join(src_code.splitlines()[extractor.def_start - 1: extractor.def_end]),
            self.class_or_func_name,
            self.relative_src_path,
        )
        wrapper = cst.metadata.MetadataWrapper(cst.parse_module(dest_code))
        dest_tree = wrapper.visit(inserter)

        with open(self.dest_file_path, "w") as file:
            file.write(dest_tree.code)
        self.update_imports()

    def update_imports(self) -> None:
        for root, dirs, files in os.walk(self.project_root):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    if file_path in {self.src_file_path, self.dest_file_path}:
                        continue
                    with open(file_path, "r") as file:
                        file_code = file.read()
                    tree = cst.parse_module(file_code)
                    updater = ImportUpdater(self.class_or_func_name, self.relative_src_path, self.relative_dest_path)
                    updated_tree = tree.visit(updater)

                    with open(file_path, "w") as file:
                        file.write(updated_tree.code)


mover = Mover(
    "./tests/fixtures/mover_test2_expected",
    "./tests/fixtures/mover_test2_expected/dir/subdir/file1.py",
    "./tests/fixtures/mover_test2_expected/file3.py",
    "SomeClass",
)
mover.move()
