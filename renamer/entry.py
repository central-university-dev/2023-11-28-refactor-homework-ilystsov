from pathlib import Path

import libcst
from libcst import matchers

class RenameTransformer(libcst.CSTTransformer):

    def __init__(self, old_name, target_name):
        self._old_name = old_name
        self._target_name = target_name
        self._restore_keywords = []

    def _rename(self, original_node, renamed_node):
        if original_node.value == self._old_name:
            return renamed_node.with_changes(value=self._target_name)
        else:
            return renamed_node

    def leave_Name(self, original_node, renamed_node):
        return self._rename(original_node, renamed_node)

    def visit_Arg(self, node):
        if node.keyword and node.keyword.value == self._old_name:
            self._restore_keywords.append(node.keyword.value)
        return True

    def leave_Arg(self, original_node, renamed_node):
        try:
            restore = self._restore_keywords.pop()
            return renamed_node.with_changes(keyword=renamed_node.keyword.with_changes(value=restore))
        except IndexError:
            return renamed_node


def rename_variable(source_code: str, old_name: str, target_name: str) -> str:
    rename_transformer = RenameTransformer(old_name, target_name)
    original_tree = libcst.parse_module(source_code)
    renamed_tree = original_tree.visit(rename_transformer)
    return renamed_tree.code
