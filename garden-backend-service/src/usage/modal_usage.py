#!/usr/bin/env python
# -*- coding: utf-8 -*-

import modal
from modal.gpu import (
    A10G,
    A100,
    H100,
    L4,
    T4,
)

MODAL_PRICES = {
    # see: https://modal.com/pricing
    H100: 0.001644,  # per GPU per second
    A100: 0.001319,  # TODO figure out how to include the cheaper A100 variant
    A10G: 0.000306,
    L4: 0.000222,
    T4: 0.000164,
    "memory": 0.00000667,  # per GB
    "cpu": 0.000038,  # per core per second
}


def estimate_usage(
    func: modal.Function,
    exec_time_seconds: float,
) -> float:
    """Estimate billable usage for a Modal function invocation."""
    spec = func.spec
    cpus = spec.cpu
    gpus = [modal.gpu._parse_gpu_config(gpu) for gpu in spec.gpus] if spec.gpus else []
    # use the memory limit if provided, see: https://modal.com/docs/guide/resources#memory
    mem = spec.memory[1] if isinstance(spec.memory, tuple) else spec.memory
    # memory is specified in MB, but billed in GB
    # do the conversion before calculating usage
    mem = mem / 1024 if mem else 1

    gpu_usage = sum(
        [(MODAL_PRICES[gpu.__class__] * exec_time_seconds) * gpu.count for gpu in gpus]
    )
    cpu_usage = cpus * MODAL_PRICES["cpu"] * exec_time_seconds
    mem_usage = mem * MODAL_PRICES["memory"] * exec_time_seconds

    return gpu_usage + cpu_usage + mem_usage
