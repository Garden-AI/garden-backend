from collections.abc import Sequence

import modal
from modal.gpu import (
    A10G,
    A100,
    H100,
    L4,
    T4,
)

from src.models.modal.modal_function import ModalFunction

DEFAULT_CPUS = 0.125
DEFAULT_MEMORY_MB = 256

# see: https://modal.com/pricing
MODAL_PRICES = {
    H100: 0.001267,  # per GPU per second
    A100: 0.000944,  # TODO figure out how to include the cheaper A100 variant
    A10G: 0.000306,
    L4: 0.000222,
    T4: 0.000164,
    "memory": 0.00000667,  # per GB per second
    "cpu": 0.000038,  # per core per second
}


def estimate_usage(
    modal_func: ModalFunction,
    exec_time_seconds: float,
) -> float:
    """Estimate billable usage for a Modal function invocation.

    Calculates a rough estimate of usage based on the funcion's hardware spec and execution time.
    see: https://modal.com/pricing
    """
    spec = modal_func.hardware_spec or {}

    cpus = spec.get("cpu") or DEFAULT_CPUS
    cpu_usage = cpus * MODAL_PRICES.get("cpu", 0) * exec_time_seconds

    # gpus are either a list, a sinlge gpu, or None
    gpu_spec = spec.get("gpus") or []
    if isinstance(gpu_spec, list):
        # assume the most expensive gpu in the list
        gpus = [modal.gpu._parse_gpu_config(gpu) for gpu in gpu_spec]
        gpu = max(
            gpus, key=lambda gpu: MODAL_PRICES.get(gpu.__class__, 0), default=None
        )
    else:
        gpu = modal.gpu._parse_gpu_config(gpu_spec)
    gpu_usage = (
        MODAL_PRICES.get(gpu.__class__, 0) * exec_time_seconds * gpu.count if gpu else 0
    )

    mem_spec = spec.get("memory") or DEFAULT_MEMORY_MB
    # use the memory limit if provided
    # see: https://modal.com/docs/guide/resources#memory
    mem = mem_spec[-1] if isinstance(mem_spec, Sequence) else mem_spec
    # memory is specified in MB, but billed in GB
    # do the conversion before calculating usage
    mem = mem / 1024
    mem_usage = mem * MODAL_PRICES.get("memory", 0) * exec_time_seconds

    return gpu_usage + cpu_usage + mem_usage
