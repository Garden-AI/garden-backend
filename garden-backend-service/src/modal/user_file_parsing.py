import ast
import copy
from dataclasses import dataclass, field

import modal
from src.exceptions.modal import ModalException

IMAGE_FACTORY_METHOD_BLOCKLIST = {
    # anything that would work w/ user's local modal client but not via garden
    "pip_install_private_repos",
    "copy_mount",
    "copy_local_file",
    "copy_local_dir",
    "pip_install_from_requirements",
    "pip_install_from_pyproject",
    "poetry_install_from_file",
    "from_dockerfile",
}

FUNCTION_KWARG_BLOCKLIST = {
    # kwargs not allowed in the @app.function(...) decorator
    "schedule",
    "secrets",
    "mounts",
    "network_file_systems",
    "allow_cross_region_volumes",
    "proxy",
    "keep_warm",
    "is_generator",
    "cloud",
    "region",
    "block_network",
}

MODAL_IMAGE_BUILDER_VERSION = "2024.10"


@dataclass
class ModalImageInfo:
    base_image: str | None = None
    python_version: str = "3.12"
    pip_requirements: list[str] = field(default_factory=list)
    conda_requirements: list[str] = field(default_factory=list)


def _image_default() -> ModalImageInfo:
    # helper for use with default_factory below
    call_node = ast.parse("modal.Image.debian_slim()").body[0].value
    return try_parse_image_info(call_node, parsed_images={})


@dataclass
class ModalAppInfo:
    app_identifier: str  # variable name of the app
    app_name: str | None = None  # literal str given to the modal.App constructor
    image: ModalImageInfo = field(default_factory=_image_default)


@dataclass
class ModalFunctionInfo:
    function_name: str
    function_text: str
    function_desc: str
    app: ModalAppInfo
    image: ModalImageInfo


@dataclass
class ModalLocalEntrypointInfo:
    function_name: str
    function_text: str
    called_functions: set[str] = field(default_factory=set)


@dataclass
class ModalFileParseResults:
    images: list[ModalImageInfo] = field(default_factory=list)
    apps: list[ModalAppInfo] = field(default_factory=list)
    functions: list[ModalFunctionInfo] = field(default_factory=list)
    local_entrypoints: list[ModalLocalEntrypointInfo] = field(default_factory=list)


def _validate_module_level_imports(tree: ast.Module) -> None:
    from .utils import is_stdlib_module  # moved import here to avoid circular import

    """Check that there are no module-level imports other than 'import modal' or stdlib imports."""
    for node in tree.body:
        match node:
            case ast.Import(names=names):
                for alias in names:
                    if alias.name != "modal" and not is_stdlib_module(alias.name):
                        raise ModalException(
                            detail=f"Module-level import '{alias.name}' is not allowed.",
                            suggested_fix="Place all imports other than 'import modal' or stdlib imports inside function or class scopes.",
                        )
            case ast.ImportFrom(module=module_name):
                # Only allow if module_name is 'modal' or a valid stdlib module
                if module_name is None or (
                    module_name != "modal" and not is_stdlib_module(module_name)
                ):
                    raise ModalException(
                        detail=f"Module-level import 'from {module_name}' is not allowed.",
                        suggested_fix="Place all imports other than 'import modal' or stdlib imports inside function or class scopes.",
                    )


def parse_modal_file(contents: str) -> ModalFileParseResults:
    """Parse the contents of a user's modal file into image/app/function metadata.

    This does not exec untrusted code. It scans the ast for top-level assignment or function nodes, and
    extracts metadata from any nodes that are shaped like an image, app, or function, respectively.

    """
    try:
        tree = ast.parse(contents)
    except SyntaxError as e:
        raise ModalException(
            detail=f"Could not parse Modal file: {str(e)}",
            suggested_fix="Make sure the Modal file is valid Python code.",
        )

    # Validate that there are no disallowed module-level imports
    _validate_module_level_imports(tree)

    images = {}
    apps = {}
    functions = {}
    local_entrypoints = []

    for node in tree.body:
        match node:
            # Case 1: assigning a Modal image to a variable
            case ast.Assign(
                targets=[ast.Name(id=image_name)], value=ast.Call() as call_node
            ) if image_info := try_parse_image_info(call_node, images):
                images[image_name] = image_info

            # Case 2: assigning a Modal app to a variable
            case ast.Assign() as assign_node if app_info := try_parse_app_info(
                assign_node, images
            ):
                apps[app_info.app_identifier] = app_info

            # Case 3: defining a Modal function
            case (
                ast.FunctionDef() as func_def
            ) if function_info := try_parse_function_info(func_def, images, apps):
                functions[function_info.function_name] = function_info
            # Case 4: defining a modal function as a method on a class
            case (
                ast.ClassDef() as class_def
            ) if class_function_infos := try_parse_class_function_info(
                class_def, images, apps
            ):
                for function_info in class_function_infos:
                    functions[function_info.function_name] = function_info
            case (
                ast.FunctionDef() as local_ep_def
            ) if local_entrypoint_info := try_parse_local_entrypoint_info(
                local_ep_def, functions
            ):
                local_entrypoints += [local_entrypoint_info]

    if "app" not in apps:
        raise ModalException(
            detail="No Modal App named 'app' found in file.",
            suggested_fix="Make sure Modal App variable is named 'app'. e.g. 'app =  modal.App(...)'",
        )

    return ModalFileParseResults(
        images=list(images.values()),
        apps=list(apps.values()),
        functions=list(functions.values()),
        local_entrypoints=local_entrypoints,
    )


# image info helpers
def try_parse_image_info(
    node: ast.Call,
    parsed_images: dict[str, ModalImageInfo],
    _info=None,
) -> ModalImageInfo | None:
    """Return a ModalImageInfo object if the given Call node constructs a modal Image, otherwise return None."""
    info = _info or ModalImageInfo()

    if not isinstance(node, ast.Call):
        raise TypeError(f"Expected `ast.Call` node, not {type(node)}.")

    match node.func:
        # base case: the call node is the root image factory method, like `modal.Image.<factory_method>` or `Image.<factory_method>`
        case (
            ast.Attribute(value=ast.Name(id="Image"))
            | ast.Attribute(
                value=ast.Attribute(value=ast.Name(id="modal"), attr="Image")
            )
        ):
            return _update_image_info_from_root_staticmethod(node, info)
        # base case 2: method chained on an existing image variable, like `my_img = my_base_image.<factory_method>`
        case ast.Attribute(value=ast.Name(id=image_var)) if image_var in parsed_images:
            base_info = parsed_images[image_var]
            new_info = _update_image_info_from_factory_method(node, base_info)
            new_info.pip_requirements.extend(info.pip_requirements)
            new_info.conda_requirements.extend(info.conda_requirements)
            return new_info
        # recursive case: chained method, the value of the attribute node is another call node
        case ast.Attribute(value=ast.Call() as next_node):
            info = _update_image_info_from_factory_method(node, info)
            return try_parse_image_info(next_node, parsed_images, info)
        # otherwise, this call node doesn't construct a valid modal image
        case _:
            return None


def _update_image_info_from_root_staticmethod(
    node: ast.Call, info: ModalImageInfo
) -> ModalImageInfo:
    """helper: update the info object from the root call node for an image, e.g. the `Image.debian_slim` or `Image.micromamba` call"""
    new_info = copy.deepcopy(info)

    match node:
        # Case 1: constructed with `Image.from_registry`
        case ast.Call(
            func=ast.Attribute(attr="from_registry"),
            args=[arg],
            keywords=keywords,
        ):
            match arg:
                # case 1a: image is referred to by a plain string
                case ast.Constant(value=str(base_image_tag)):
                    # save the explicit base image
                    new_info.base_image = base_image_tag
                case _:
                    # else, if the arg is not a constant (e.g. it's an f-string or variable)
                    # we can't reliably infer a base image
                    new_info.base_image = "n/a"
            for kw in keywords:
                if kw.arg == "add_python" and isinstance(kw.value, ast.Constant):
                    new_info.python_version = str(kw.value.value)
        # Case 2: constructed with `Image.debian_slim`
        case ast.Call(
            func=ast.Attribute(attr="debian_slim"),
            keywords=keywords,
        ):
            python_version = info.python_version
            for kw in keywords:
                if kw.arg == "python_version" and isinstance(kw.value, ast.Constant):
                    python_version = str(kw.value.value)

            python_version_full = modal.image._dockerhub_python_version(
                MODAL_IMAGE_BUILDER_VERSION, python_version
            )
            debian_codename = modal.image._base_image_config(
                "debian", MODAL_IMAGE_BUILDER_VERSION
            )

            new_info.python_version = python_version_full
            new_info.base_image = f"python:{python_version_full}-slim-{debian_codename}"

        # Case 3: constructed with `Image.micromamba`
        case ast.Call(
            func=ast.Attribute(attr="micromamba"),
            keywords=keywords,
        ):
            new_info.python_version = info.python_version
            for kw in keywords:
                if kw.arg == "python_version" and isinstance(kw.value, ast.Constant):
                    new_info.python_version = str(kw.value.value)
            micromamba_version = modal.image._base_image_config(
                "micromamba", MODAL_IMAGE_BUILDER_VERSION
            )
            debian_codename = modal.image._base_image_config(
                "debian", MODAL_IMAGE_BUILDER_VERSION
            )
            new_info.base_image = (
                f"mambaorg/micromamba:{micromamba_version}-{debian_codename}-slim"
            )
        case _:
            raise ModalException(
                detail="Failed to parse image info: expected modal Image to be constructed with one of `debian_slim`, `micromamba`, or `from_registry` staticmethods."
            )
    return new_info


def _update_image_info_from_factory_method(
    node: ast.Call, info: ModalImageInfo
) -> ModalImageInfo:
    """helper: update info object from a chained method call node"""

    new_info = copy.deepcopy(info)
    match node:
        case ast.Call(
            func=ast.Attribute(attr="pip_install"),
            args=args,
        ):
            for arg in args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    new_info.pip_requirements.append(arg.value)

        case ast.Call(
            func=ast.Attribute(attr="micromamba_install"),
            args=args,
        ):
            for arg in args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    new_info.conda_requirements.append(arg.value)
        case ast.Call(func=ast.Attribute(attr=method_name)):
            if method_name in IMAGE_FACTORY_METHOD_BLOCKLIST:
                raise ModalException(
                    detail=f"Garden can't publish modal images using {method_name} on behalf of user."
                )
    return new_info


# app info helpers
def try_parse_app_info(
    node: ast.Assign,
    parsed_images: dict[str, ModalImageInfo] | None = None,
) -> ModalAppInfo | None:
    match node:
        case ast.Assign(
            targets=[ast.Name(id=app_identifier)],
            value=(
                ast.Call(func=ast.Attribute(value=ast.Name(id="modal"), attr="App"))
                | ast.Call(func=ast.Name(id="App"))
            ) as call_node,
        ):
            info = ModalAppInfo(app_identifier)
            return _update_app_info_from_constructor(call_node, info, parsed_images)
        case _:
            return None


def _update_app_info_from_constructor(
    node: ast.Call,
    info: ModalAppInfo,
    parsed_images: dict[str, ModalImageInfo] | None = None,
) -> ModalAppInfo:
    app_info = copy.deepcopy(info)
    parsed_images = parsed_images or {}  # in case image is specified by identifier
    match node:
        case ast.Call(args=[ast.Constant(value=str(app_name_literal))]):
            app_info.app_name = app_name_literal

    match node:
        case ast.Call(keywords=keywords):
            for kw in keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                    app_info.app_name = kw.value.value
                if kw.arg == "image" and isinstance(kw.value, ast.Name):
                    # handle case where kwarg is `image=my_image_variable`
                    image_name = kw.value.id
                    image_info = parsed_images.get(image_name)
                    app_info.image = image_info
                elif kw.arg == "image" and isinstance(kw.value, ast.Call):
                    # handle case where kwarg is `image=modal.Image.<chained_image_methods>`
                    image_info = try_parse_image_info(kw.value, parsed_images)
                    app_info.image = image_info

                # TODO disallow other kwargs? (volumes, etc)
    return app_info


# function info helpers
def try_parse_function_info(
    node: ast.FunctionDef,
    parsed_images: dict[str, ModalImageInfo] | None = None,
    parsed_apps: dict[str, ModalAppInfo] | None = None,
) -> ModalFunctionInfo | None:
    parsed_images = parsed_images or {}
    parsed_apps = parsed_apps or {}
    match node:
        case ast.FunctionDef(
            name=function_name,
            decorator_list=[  # NB: assumes decorator is the first one if there are multiple
                ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id=app_identifier), attr="function"
                    )
                ) as decorator_node,
                *_,
            ],
        ) if app_identifier in parsed_apps:
            # if we're parsing `@myapp.function(...)`, we've already seen `myapp`
            app_info = parsed_apps[app_identifier]
            function_info = ModalFunctionInfo(
                function_name=function_name,
                function_text=ast.unparse(node),
                function_desc=ast.get_docstring(node) or "",
                app=app_info,
                image=app_info.image,  # default is app image, but decorator kwarg takes priority
            )

            return _update_function_info_from_decorator(
                decorator_node, function_info, parsed_images, parsed_apps
            )
        case _:
            return None


def _update_function_info_from_decorator(
    node: ast.Call,
    info: ModalFunctionInfo,
    parsed_images: dict[str, ModalImageInfo] | None = None,
    parsed_apps: dict[str, ModalAppInfo] | None = None,
) -> ModalFunctionInfo:
    parsed_images = parsed_images or {}
    func_info = copy.deepcopy(info)
    for kw in node.keywords:
        match kw:
            case ast.keyword(arg="image", value=ast.Name()):
                # handle case where kwarg is `image=my_image_variable`
                image_name = kw.value.id
                image_info = parsed_images.get(image_name, func_info.image)
                func_info.image = image_info
            case ast.keyword(arg="image", value=ast.Call()):
                # handle case where kwarg is `image=modal.Image.<chained_image_methods>`
                image_info = try_parse_image_info(kw.value, parsed_images)
                if image_info is None:
                    func_info.image = _image_default()  # default is sane if this fails, no need to error and stop the publish attempt
                else:
                    func_info.image = image_info
            case ast.keyword(arg="name", value=ast.Constant(value=str(new_name))):
                func_info.function_name = new_name
            case ast.keyword(arg=arg) if arg in FUNCTION_KWARG_BLOCKLIST:
                raise ModalException(
                    detail=f"Garden doesn't support the use of {arg} in modal functions."
                )
    return func_info


def try_parse_class_function_info(
    node: ast.ClassDef,
    parsed_images: dict[str, ModalImageInfo] | None = None,
    parsed_apps: dict[str, ModalAppInfo] | None = None,
) -> list[ModalFunctionInfo] | None:
    """Parse a class decorated with @app.cls into ModalFunctionInfo objects for each @modal.method."""
    parsed_images = parsed_images or {}
    parsed_apps = parsed_apps or {}

    match node:
        case ast.ClassDef(
            name=class_name,
            decorator_list=[
                ast.Call(
                    func=ast.Attribute(value=ast.Name(id=app_identifier), attr="cls")
                ) as decorator_node,
                *_,
            ],
        ) if app_identifier in parsed_apps:
            app_info = parsed_apps[app_identifier]
            class_image = (
                app_info.image
            )  # default is same as app unless specified by kwarg
            functions = []

            for kw in decorator_node.keywords:
                match kw:
                    case ast.keyword(arg=arg) if arg in FUNCTION_KWARG_BLOCKLIST:
                        raise ModalException(
                            detail=f"Garden doesn't support the use of {arg} in modal functions."
                        )
                    case ast.keyword(arg="image", value=ast.Name()):
                        image_name = kw.value.id
                        class_image = parsed_images.get(image_name) or class_image
                    case ast.keyword(arg="image", value=ast.Call()):
                        class_image = try_parse_image_info(kw.value, parsed_images)

            # Collect all methods decorated with @modal.method()
            for method in node.body:
                match method:
                    case ast.FunctionDef(
                        name=method_name,
                        decorator_list=[
                            ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id="modal"), attr="method"
                                )
                            ),
                            *_,
                        ],
                    ):
                        # Create ModalFunctionInfo for this method
                        function_info = ModalFunctionInfo(
                            function_name=f"{class_name}.{method_name}",
                            function_text=ast.unparse(method),
                            function_desc=ast.get_docstring(method) or "",
                            app=app_info,
                            image=class_image,
                        )
                        functions.append(function_info)

            return functions or None
        case _:
            return None


def try_parse_local_entrypoint_info(
    node: ast.FunctionDef,
    parsed_functions: dict[str, ModalFunctionInfo] | None = None,
) -> ModalLocalEntrypointInfo | None:
    parsed_functions = parsed_functions or {}
    match node:
        case ast.FunctionDef(name=entrypoint_name) if _is_decorated_local_entrypoint(
            node
        ):
            entrypoint_info = ModalLocalEntrypointInfo(
                function_name=entrypoint_name,
                function_text=ast.unparse(node),
            )
            return _update_entrypoint_info_from_decorator(
                node, entrypoint_info, set(parsed_functions.keys())
            )
        case _:
            return None


def _is_decorated_local_entrypoint(node: ast.FunctionDef) -> bool:
    """Check if a function node is decorated like @<some_app>.local_entrypoint."""
    for decorator in node.decorator_list:
        match decorator:
            case ast.Call(ast.Attribute(attr="local_entrypoint")):
                return True
    return False


def _update_entrypoint_info_from_decorator(
    fn_node: ast.FunctionDef,
    info: ModalLocalEntrypointInfo,
    known_function_names: set[str],
) -> ModalLocalEntrypointInfo:
    ep_info = copy.deepcopy(info)
    # walk the function node's subtree for any Calls which match the name of a
    # function (or method) we've already seen
    for node in ast.walk(fn_node):
        match node:
            # case 1: function_name.remote()
            case ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id=called_function_name), attr="remote"
                )
            ) if called_function_name in known_function_names:
                ep_info.called_functions |= {called_function_name}
            # case 2: class_name.method_name.remote()
            case ast.Call(
                func=ast.Attribute(
                    value=ast.Attribute(
                        value=ast.Name(id=class_name), attr=method_name
                    ),
                    attr="remote",
                )
            ) if f"{class_name}.{method_name}" in known_function_names:
                ep_info.called_functions |= {f"{class_name}.{method_name}"}
    return ep_info
