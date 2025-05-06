from src.api.schemas.modal.invocations import (
    ModalInvocationOutputsResponse,
    ModalInvocationRequest,
)


class BenchmarkRequest(ModalInvocationRequest):
    # The id of the benchmark to run, for now it is a modal function id
    benchmark_id: int
    # The id of the benchmarking task to run, i.e. Benchmark: MatBecnch Discovery -> Task: IS2RE
    task_id: int
    # The id of the function to benchmark
    function_id: int


class BenchmarkResult(ModalInvocationOutputsResponse):
    # the id of the benchmark to run, for now it is a modal function id
    benchmark_id: int

    # the id of the function benchmarked
    function_id: int
