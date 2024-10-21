import modal
import pytest

from src.sandboxed_functions.modal_publishing_helpers import get_function_specs

app = modal.App()


@app.function()
def hello():
    return "Hello, world!"


@app.function(cpu=4.0, gpu="A10G", memory=(1024, 2048))
def hello_with_specs():
    return "Hello, world!"


def test_get_function_specs_raises_on_invalid_key():
    """Confirms that we will get errors when Modal changes their `_FunctionSpec` schema"""
    invalid_specs = ["some", "specs", "that" "dont", "exist"]
    with pytest.raises(KeyError):
        get_function_specs(app.registered_functions, invalid_specs)


def test_get_function_specs_parses_specs_correctly():
    specs = ["gpus", "cpu", "memory"]
    specs = get_function_specs(app.registered_functions, specs)

    parsed_specs = specs["hello_with_specs"]
    assert parsed_specs["cpu"] == 4.0
    assert parsed_specs["gpus"] == "A10G"
    assert parsed_specs["memory"] == (1024, 2048)
