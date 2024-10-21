from src.models.modal.modal_function import ModalFunction
from src.usage.modal_usage import estimate_usage


def test_estimate_usage():
    cheap_specs = {"cpu": None, "gpus": None, "memory": None}
    expensive_specs = {"cpu": 8.0, "gpus": "A10G", "memory": (4096, 8192)}
    expensive_specs_double_gpu = {
        "cpu": 8.0,
        "gpus": ["A10G", "A10G"],
        "memory": (4096, 8192),
    }
    # when we have a list of gpus, it should assume the more expensive gpu
    really_expensive_specs = {
        "cpu": 8.0,
        "gpus": ["A10G", "A100"],
        "memory": (4096, 8192),
    }

    cheap_func = ModalFunction(hardware_spec=cheap_specs)
    expensive_func = ModalFunction(hardware_spec=expensive_specs)
    expensive_func_double_gpu = ModalFunction(hardware_spec=expensive_specs_double_gpu)
    really_expensive_func = ModalFunction(hardware_spec=really_expensive_specs)

    cheap_usage = estimate_usage(cheap_func, 30)
    expensive_usage = estimate_usage(expensive_func, 30)
    expensive_usage_double_gpu = estimate_usage(expensive_func_double_gpu, 30)
    really_expensive_usage = estimate_usage(really_expensive_func, 30)

    assert cheap_usage > 0
    assert cheap_usage < expensive_usage
    assert expensive_usage == expensive_usage_double_gpu
    assert expensive_usage < really_expensive_usage
