import modal

from src.sandboxed_functions.modal_publishing_helpers import get_function_specs
from src.usage.modal_usage import estimate_usage

app = modal.App()


@app.function(cpu=8, gpu=["A100"], memory=(4096, 8192))
def expensive_func():
    return "Hello, world!"


@app.function()
def cheap_func():
    return "Hello, world!"


def test_estimate_usage():
    specs = get_function_specs(app.registered_functions, ["gpus", "cpu", "memory"])

    expensive_usage = estimate_usage(specs["expensive_func"], 30)
    cheap_usage = estimate_usage(specs["cheap_func"], 30)

    assert cheap_usage > 0
    assert cheap_usage < expensive_usage
