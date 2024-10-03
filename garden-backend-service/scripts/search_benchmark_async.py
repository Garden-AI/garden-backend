import asyncio
from time import perf_counter

import httpx
from rich.console import Console

url = "http://localhost:5500/gardens/search"
payload = {
    "q": "material science",
    "limit": 10,
    "offset": 5,
    "filters": [{"field_name": "authors", "values": ["will engler"]}],
}
headers = {"Content-Type": "application/json"}
iterations = 10

console = Console()


async def send_request(url, payload, headers, client, iteration):
    """Send a single HTTP POST request asynchronously and measure the response time."""
    start_time = perf_counter()
    response = await client.post(url, json=payload, headers=headers)
    response_time = (perf_counter() - start_time) * 1000  # Convert to milliseconds

    if response.status_code != 200:
        raise ValueError(f"Request failed: {response.reason_phrase}\n{response.text}")

    console.print(f"Iteration {iteration + 1}: [cyan]{response_time:.2f} ms[/cyan]")
    return response_time


async def benchmark_route(url, payload, headers, iterations):
    """Run the benchmark asynchronously using httpx."""
    total_time = 0.0

    console.print(f"[bold green]Benchmarking API Route (Async):[/bold green] {url}")

    # Using a single client session for better performance
    async with httpx.AsyncClient() as client:
        # Schedule all requests to run concurrently
        tasks = [
            send_request(url, payload, headers, client, i) for i in range(iterations)
        ]
        response_times = await asyncio.gather(*tasks)

    total_time = sum(response_times)
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
    asyncio.run(benchmark_route(url, payload, headers, iterations))
