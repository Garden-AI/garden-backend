import pytest

from src.exceptions.modal import ModalException
from src.modal.user_file_parsing import parse_modal_file


def test_parse_modal_file_accepts_modal_import():
    contents = """
import modal

app = modal.App("my-app")

@app.function()
def hello():
    return "Hello World"
    """
    result = parse_modal_file(contents)
    assert len(result.functions) == 1
    assert result.functions[0].function_name == "hello"


def test_parse_modal_file_accepts_from_modal_import():
    contents = """
from modal import App, Image

app = App("my-app")

@app.function()
def hello():
    return "Hello World"
    """
    result = parse_modal_file(contents)
    assert len(result.functions) == 1
    assert result.functions[0].function_name == "hello"


def test_parse_modal_file_rejects_non_modal_import():
    contents = """
import modal
import numpy as np

app = modal.App("my-app")

@app.function()
def hello():
    return "Hello World"
    """
    with pytest.raises(ModalException) as excinfo:
        parse_modal_file(contents)
    assert "Module-level import 'numpy' is not allowed" in str(excinfo.value.detail)


def test_parse_modal_file_rejects_non_modal_from_import():
    contents = """
import modal
from numpy import array

app = modal.App("my-app")

@app.function()
def hello():
    return "Hello World"
    """
    with pytest.raises(ModalException) as excinfo:
        parse_modal_file(contents)
    assert "Module-level import 'from numpy' is not allowed" in str(
        excinfo.value.detail
    )


def test_parse_modal_file_allows_function_scope_imports():
    contents = """
import modal

app = modal.App("my-app")

@app.function()
def hello():
    import numpy as np
    from pandas import DataFrame
    return "Hello World"
    """
    result = parse_modal_file(contents)
    assert len(result.functions) == 1
    assert result.functions[0].function_name == "hello"


def test_parse_modal_file_allows_class_scope_imports():
    contents = """
import modal

app = modal.App("my-app")

@app.cls()
class MyClass:
    import numpy as np
    from pandas import DataFrame

    @modal.method()
    def method(self):
        return "Hello World"
    """
    result = parse_modal_file(contents)
    assert len(result.functions) == 1
    assert result.functions[0].function_name == "MyClass.method"


def test_parse_modal_file_accepts_stdlib_import():
    contents = """
import sys
import modal

app = modal.App("my-app")

@app.function()
def hello():
    return sys.version
    """
    result = parse_modal_file(contents)
    assert len(result.functions) == 1
    assert result.functions[0].function_name == "hello"


def test_parse_modal_file_accepts_stdlib_from_import():
    contents = """
from os import path
import modal

app = modal.App("my-app")

@app.function()
def hello():
    return path.join("a", "b")
    """
    result = parse_modal_file(contents)
    assert len(result.functions) == 1
    assert result.functions[0].function_name == "hello"


def test_parse_modal_file_rejects_nonexistent_module():
    contents = """
import modal
import definitelynotamodule

app = modal.App("my-app")

@app.function()
def hello():
    return "Hello World"
    """
    with pytest.raises(ModalException) as excinfo:
        parse_modal_file(contents)
    assert "Module-level import 'definitelynotamodule' is not allowed" in str(
        excinfo.value.detail
    )
