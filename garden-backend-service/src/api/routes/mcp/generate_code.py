import ast
import structlog

from sqlalchemy import select

from src.api.dependencies.database import get_db_session_maker, get_settings
from src.models import ModalFunction
from src.models.modal.modal_function import ModalFunction
from src.api.routes.mcp.mcp_server import mcp

logger = structlog.get_logger()

@mcp.tool()
async def generate_code(garden_model_doi: str, function_id: int):
    settings = get_settings()
    session_maker = await get_db_session_maker(settings)

    try:
        async with session_maker() as db:
            stmt = select(ModalFunction).where(
                ModalFunction.id == function_id
            )

            result = await db.scalar(stmt)

            if result is None:
                raise ValueError("Function id is not valid")
    except Exception as e:
        logger.error(e)
        return f"Error: {str(e)}"
    
    ret = {
        "response_type": "garden_client_code_generation",
        "imports": ["from garden_ai import GardenClient"],
    }
    function_metadata = {
        "function_signature": f"my_garden.{result.function_name}",
        "parameters": _parse_function_signature(_extract_function_signature(result.function_text)),
        "doi": garden_model_doi,
        "description": result.description,
        "function_text": result.function_text,
        "common_implementation": "from garden_ai import GardenClient\nclient = GardenClient()\nmy_garden = client.get_garden(doi)\nmy_garden.my_function(my_params)"
    }

    ret["function_metadata"] = function_metadata

    return ret

@mcp.prompt("generate-code-prompt")
def generate_code_prompt():
    return "Generate minimal code, only what is necessary. Don't output or print anything unless specified by the user."

@mcp.resource("resource://code_examples")
async def code_examples():
    settings = get_settings()
    session_maker = await get_db_session_maker(settings)

    try:
        async with session_maker() as db:
            stmt = select(ModalFunction)

            result = await db.scalars(stmt.limit(40))

            functions = result.all()

            examples = {}
            for func in functions:
                if func.example_usage:
                    examples[func.function_name] = func.example_usage

            return examples
        
    except Exception as e:
        logger.error(e)
        return f"Error: {str(e)}"

def _extract_function_signature(code: str):
    lines = code.splitlines()
    signature_lines = []
    collecting = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("def "):
            collecting = True

        if collecting:
            signature_lines.append(line)
            if stripped.endswith(":"):
                break

    return " ".join(signature_lines).strip()

def _parse_function_signature(func_dec: str):
    if func_dec.endswith(":"):
        func_dec += "\n\tpass"

    tree = ast.parse(func_dec)

    function_params = []
    for node in ast.walk(tree):
         if isinstance(node, ast.FunctionDef):
            args = node.args.args
            defaults = node.args.defaults
            # Fill missing defaults with None
            num_missing_defaults = len(args) - len(defaults)
            defaults = [None] * num_missing_defaults + defaults

            param_list = []
            for arg, default in zip(args, defaults):
                param_info = {
                    "name": arg.arg,
                    "type": ast.unparse(arg.annotation) if arg.annotation else None,
                    "default": ast.unparse(default) if default else None
                }
                param_list.append(param_info)

            function_params.append(param_list)

    return function_params