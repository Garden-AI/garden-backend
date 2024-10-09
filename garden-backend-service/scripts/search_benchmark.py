import time

import requests
from rich.console import Console

url = "http://localhost:5500/gardens/search"
payload = {
    "q": "material science",
    "limit": 10,
    "offset": 5,
    "filters": [{"field_name": "authors", "values": ["will engler"]}],
}
headers = {"Content-Type": "application/json"}
iterations = 100

console = Console()


def benchmark_route(url, payload, headers, iterations):
    total_time = 0.0

    console.print(f"[bold green]Benchmarking API Route:[/bold green] {url}")

    for i in range(iterations):
        try:
            start_time = time.time()
            response = requests.post(url, json=payload, headers=headers)
            response_time = (time.time() - start_time) * 1000  # Response time in ms

            if response.status_code != 200:
                raise ValueError(f"Request failed: {response.reason}\n{response.text}")

            total_time += response_time
            console.print(f"Iteration {i + 1}: [cyan]{response_time:.2f} ms[/cyan]")

        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Request failed:[/bold red] {e}")
            return

    average_time = total_time / iterations
    console.print(
        f"\n[bold green]Benchmark Completed[/bold green]: {iterations} iterations"
    )
    console.print(
        f"Average Response Time: [bold yellow]{average_time:.2f} ms[/bold yellow]"
    )
    console.print(
        f"Total Benchmark Duration: [bold yellow]{total_time:.2f} ms[/bold yellow]"
    )


if __name__ == "__main__":
    benchmark_route(url, payload, headers, iterations)
