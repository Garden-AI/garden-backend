# Tests

## Structure

The structure of the tests module mirrors the structure of the `src/` directory:

``` text
garden-backend-service
└── tests # you are here
    ├── api
    │   └── routes
    │       ├── test_docker_push_token.py
    │       ├── test_doi.py
    │       ├── test_entrypoint.py
    │       ├── test_garden.py
    │       ├── test_greet.py
    │       ├── test_notebook.py
    │       └── test_routes.py
    ├── auth
    │   └── test_globus_groups.py
    ├── conftest.py
    ├── fixtures
    │   ├── EntrypointCreateRequest-shared-entrypoint.json
    │   ├── EntrypointCreateRequest-with-metadata.json
    │   ├── GardenCreateRequest-shares-entrypoint.json
    │   └── GardenCreateRequest-two-entrypoints.json
    ├── __init__.py
    └── README.md
```

For example, say you created a new module in `src/api/routes/my_routes.py`.
Corresponding tests should go in `tests/api/routes/test_my_routes.py`.

Useful fixtures are defined in `conftest.py`.

## Running the tests

Make sure the developer dependencies are installed:

``` shell
poetry install --with=develop
```

From the `garden-back-service/` directory in a poetry shell:
``` shell
pytest
```

Tests that run against the database require docker to be present and are marked with `@pytest.mark.integration`.

To skip the tests that require docker add `-m "not integration"` to your pytest command:

``` shell
pytest -m "not integration"
```
