from src.models.modal.modal_function import ModalFunction
from src.usage.modal_usage import estimate_usage


def test_estimate_usage():
    cheap_specs = {"cpu": None, "gpus": None, "memory": None}
    expensive_specs = {"cpu": 8.0, "gpus": "A100", "memory": (4096, 8192)}

    cheap_func = ModalFunction(hardware_spec=cheap_specs)
    expensive_func = ModalFunction(hardware_spec=expensive_specs)

    cheap_usage = estimate_usage(cheap_func, 30)
    expensive_usage = estimate_usage(expensive_func, 30)

    assert cheap_usage > 0
    assert cheap_usage < expensive_usage
