import libcst as cst
from libcst.metadata import QualifiedNameProvider, QualifiedNameSource
import os


def get_full_module_name(module_node: cst.Attribute | cst.Name) -> str:
    module_parts = []
    while isinstance(module_node, cst.Attribute):
        module_parts.append(module_node.attr.value)
        module_node = module_node.value
    if isinstance(module_node, cst.Name):
        module_parts.append(module_node.value)
    return ".".join(reversed(module_parts))


def resolve_relative_import(import_path: str, file_path: str) -> str:
    if not import_path.startswith("."):
        return import_path
    relative_levels = import_path.count(".")
    file_dir = os.path.dirname(file_path)
    abs_path_parts = os.path.normpath(file_dir).split(os.sep)[:-relative_levels]
    abs_path_parts += import_path.lstrip(".").split(".")
    return ".".join(abs_path_parts)


class RenameTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)

    def __init__(self, old_name: str, new_name: str) -> None:
        self.old_name = old_name
        self.new_name = new_name
        self.as_name: str | None = None

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        if original_node.value == self.old_name:
            qualified_names = self.get_metadata(QualifiedNameProvider, original_node)
            for qualified_name in qualified_names:
                if qualified_name.name in {self.old_name, self.as_name}:
                    return updated_node.with_changes(value=self.new_name)
        return updated_node

    def leave_ImportFrom(self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom) -> cst.ImportFrom:
        new_names = []
        for import_alias in original_node.names:
            if import_alias.asname and import_alias.asname.name.value == self.old_name:
                new_alias = import_alias.with_changes(asname=cst.AsName(name=cst.Name(self.new_name)))
                new_names.append(new_alias)
                module_name = get_full_module_name(original_node.module)
                self.as_name = module_name + "." + import_alias.name.value
            else:
                new_names.append(import_alias)
        return updated_node.with_changes(names=new_names)


class ImportRenameTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)

    def __init__(self, module_name: str, old_name: str, new_name: str, file_path: str) -> None:
        self.module_name = module_name
        self.old_name = old_name
        self.new_name = new_name
        self.file_path = file_path

    def leave_ImportFrom(self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom) -> cst.ImportFrom:
        module_name = get_full_module_name(original_node.module)
        if module_name == self.module_name:
            new_names = []
            for import_alias in original_node.names:
                if import_alias.name.value == self.old_name:
                    new_names.append(import_alias.with_changes(name=cst.Name(self.new_name)))
                else:
                    new_names.append(import_alias)
            return updated_node.with_changes(names=new_names)
        return updated_node

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.Attribute:
        if original_node.attr.value == self.old_name:
            qualified_names = self.get_metadata(QualifiedNameProvider, original_node.value)
            for qualified_name in qualified_names:
                if qualified_name.name == self.module_name and qualified_name.source == QualifiedNameSource.IMPORT:
                    return updated_node.with_changes(attr=cst.Name(self.new_name))
        return updated_node

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        if original_node.value == self.old_name:
            qualified_names = self.get_metadata(QualifiedNameProvider, original_node)
            for qualified_name in qualified_names:
                full_import_path = resolve_relative_import(qualified_name.name, self.file_path)
                if full_import_path == f"{self.module_name}.{self.old_name}":
                    return updated_node.with_changes(value=self.new_name)
        return updated_node


class Renamer:
    def __init__(self, project_root: str, file_path: str, old_name: str, new_name: str) -> None:
        self.project_root = project_root
        self.file_path = file_path
        self.old_name = old_name
        self.new_name = new_name

    def rename(self) -> None:
        with open(self.file_path, "r") as f:
            source_code = f.read()

        wrapper = cst.metadata.MetadataWrapper(cst.parse_module(source_code))
        renamed_tree = wrapper.visit(RenameTransformer(self.old_name, self.new_name))

        with open(self.file_path, "w") as f:
            f.write(renamed_tree.code)

        self.update_imports()

    def update_imports(self) -> None:
        relative_path = os.path.relpath(self.file_path, self.project_root)
        module_name = relative_path.replace(os.path.sep, ".").rstrip(".py")
        for root, dirs, files in os.walk(self.project_root):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)

                    with open(file_path, "r") as f:
                        source_code = f.read()

                    wrapper = cst.metadata.MetadataWrapper(cst.parse_module(source_code))
                    renamed_tree = wrapper.visit(
                        ImportRenameTransformer(module_name, self.old_name, self.new_name, self.file_path)
                    )

                    with open(file_path, "w") as f:
                        f.write(renamed_tree.code)
