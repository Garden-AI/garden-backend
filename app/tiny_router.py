# stolen from https://kevinquinn.fun/blog/tiny-python-router-for-aws-lambda/

class RouteNotFoundException(Exception):
    def __init__(self, msg: str) -> None:
        self.msg = msg
        super().__init__(self.msg)


class TinyLambdaRouter:
    def __init__(self):
        self._path_funcs = {}
        self._middlewares = []
        self.aws_event = None
        self.aws_context = None

    def middleware(self):
        def decorator(f):
            self._add_middleware(f)
            return f

        return decorator

    def _add_middleware(self, func):
        self._middlewares.append(func)

    def route(self, path, **kwargs):
        def decorator(f):
            self._add_route(path, f, **kwargs)
            return f

        return decorator

    def _add_route(self, path, func, **kwargs):
        methods = kwargs.get('methods', ['GET'])

        for method in methods:
            search_key = f'{method}-{path}'
            if self._path_funcs.get(search_key):
                raise ValueError(
                    f'Path {search_key} already registered with function {self._path_funcs.get(search_key).__name__}')

        for method in methods:
            search_key = f'{method}-{path}'
            self._path_funcs[search_key] = {'function': func, 'kwargs': kwargs}

        # print(self._path_funcs)

    def run(self, aws_event, aws_context):
        self.aws_event = aws_event
        self.aws_context = aws_context
        # assumes using ALB or Api Gateway connected to Lambda
        path = aws_event['path']
        method = aws_event['httpMethod']
        search_key = f'{method}-{path}'

        try:
            print("INITIALIZING MINI-APP. The following routes are registered.")
            print(self._path_funcs)
            print("INITIALIZED")
            path_func = self._path_funcs[search_key]['function']
            kwargs = self._path_funcs[search_key]['kwargs']
        except KeyError:
            raise RouteNotFoundException(f'No handler found for path:{search_key}')

        for m in self._middlewares:
            m(self.aws_event)

        return path_func(aws_event, aws_context, kwargs)