from pathlib import Path
from renamer.entry import rename_variable


def test():
    got = rename_variable(
        Path('tests/fixtures/source.py').read_text(),
        'arg1',
        'new_name',
    )

    assert got == Path('tests/fixtures/expected.py').read_text()
