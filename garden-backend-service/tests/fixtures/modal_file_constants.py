"""This module is just an alternative to each of the sample modal Apps getting their own file."""

# Valid case: Basic example with imported Modal symbols
VALID_BASIC_IMPORTS = """
from modal import App, Image

image = Image.debian_slim().pip_install("pandas", "numpy")
app = App("basic-imports", image=image)

@app.function(gpu="A100")
def number_crunching():
    import numpy as np
    return np.random.rand(10)
"""

# Valid case: No custom image defined (uses default)
VALID_NO_CUSTOM_IMAGE = """
import modal

app = modal.App("no-custom-image")

@app.function()
def hello_world():
    return "Hello from default image!"
"""

VALID_PYTHON_VERSION_IMAGE_KWARGS = """
import modal

my_image = modal.Image.debian_slim(python_version="3.11").pip_install("garden-ai")

my_app = modal.App("hello-modal", image=my_image)


@my_app.function(gpu=["A100", "H100"])
def hello_garden(x):
    if x:
        return "a Modal?? in the Garden-AI factory??"
    else:
        return "I guess we doin Modal now"


@my_app.function(
    image=modal.Image.debian_slim(python_version="3.12").pip_install("some-package")
)
def uh_oh(y):
    raise Exception("! At The Disco")

"""

# Valid case: Different images for different functions
VALID_MULTIPLE_IMAGES = """
import modal

# Base scientific image
sci_image = modal.Image.debian_slim().pip_install(
    "numpy",
    "scipy"
)

# Image for deep learning
dl_image = modal.Image.debian_slim().pip_install(
    "torch",
    "transformers"
)

app = modal.App("multi-image-app")

@app.function(image=sci_image)
def science_stuff():
    import numpy as np
    return np.random.rand(10)

@app.function(image=dl_image, gpu="A100")
def ml_stuff():
    import torch
    return torch.rand(10)
"""

# Valid case: Class-based Modal app
VALID_CLASS_BASED = """
import modal

image = modal.Image.debian_slim().pip_install("scikit-learn")
app = modal.App("model-app")

@app.cls(cpu=8, gpu="A100", image=image)
class Model:
    @modal.enter()
    def load_model(self):
        import pickle
        self.model = pickle.load("model.pkl")

    @modal.method()
    def predict(self, x):
        return self.model.predict(x)

    @modal.method()
    def predict_proba(self, x):
        return self.model.predict_proba(x)

@app.local_entrypoint()
def main():
    Model.predict.remote("abc")
    Model.predict_proba.remote("123")
"""

# Valid case: Different local entrypoints for different functions
VALID_MULTIPLE_LOCAL_ENTRYPOINTS = """
import modal

app = modal.App("science-app")

@app.function()
def science_stuff():
    import numpy as np
    return np.random.rand(10)

@app.local_entrypoint()
def test_science_stuff():
    print(science_stuff.remote("science r u l e s"))

@app.function()
def ml_stuff():
    import torch
    return torch.rand(10)


@app.local_entrypoint()
def test_ml_stuff():
    results = ml_stuff.remote("BILL! BILL! BILL! BILL!")
    print(results)
"""
# Valid case: Using micromamba for conda packages
VALID_CONDA_PACKAGES = """
import modal

image = modal.Image.micromamba().micromamba_install(
    "pytorch",
    "cudatoolkit",
)

app = modal.App("conda-app", image=image)

@app.function(gpu="A100")
def train_model():
    import torch
    return torch.cuda.device_count()
"""

# Invalid case: No App defined
INVALID_NO_APP = """
import modal

image = modal.Image.debian_slim().pip_install("requests")

@app.function()  # This would fail since app hasn't been defined yet
def make_request():
    import requests
    return requests.get("https://example.com").text
"""

# Invalid case: Multiple Apps defined
INVALID_MULTIPLE_APPS = """
import modal

app = modal.App("first-app")
app2 = modal.App("second-app")  # This should cause validation to fail

@app.function()
def function1():
    return "Hello from app1"

@app2.function()
def function2():
    return "Hello from app2"
"""

# Invalid case: Using disallowed image method
INVALID_IMAGE_METHOD = """
import modal

image = (modal.Image
    .debian_slim()
    .pip_install("requests")
    .pip_install_from_requirements("requirements.txt")  # This method is blocked
)

app = modal.App("invalid-image-app")

@app.function(image=image)
def my_function():
    return "Hello"
"""

# Invalid case: Using disallowed function kwarg
INVALID_FUNCTION_KWARGS = """
import modal

app = modal.App("invalid-function-app")

@app.function(secrets=["MY_SECRET"])  # secrets kwarg is not allowed
def secure_function():
    import os
    return os.environ["MY_SECRET"]
"""

VALID_MULTIPLE_IMAGE_VARIABLE_REFERENCES = """ 
import modal

# Base scientific image
SCI_IMAGE = modal.Image.debian_slim().pip_install(
    "numpy",
    "scipy"
)

# Image for deep learning
ML_IMAGE = SCI_IMAGE.pip_install(
    "torch",
    "transformers"
)

app = modal.App("multi-image-app")

@app.function(image=SCI_IMAGE)
def science_stuff():
    import numpy as np
    return np.random.rand(10)

@app.function(image=ML_IMAGE, gpu="A100")
def ml_stuff():
    import torch
    return torch.rand(10)

"""
VALID_F_STRING_FROM_REGISTRY = """
import modal

app = modal.App("valid-fstring-from-registry-app")
alignn_image = (
    modal.Image.from_registry(f"nvidia/cuda:12.4.0-devel-ubuntu22.04", add_python="3.10")
    .apt_install("git")
    .pip_install("numpy==1.26.4")
    .run_commands(
        "pip install  dgl -f https://data.dgl.ai/wheels/torch-2.4/cu124/repo.html",
        "pip install alignn"
    )
    .pip_install(
        "jarvis-tools",
        "torch==2.5.0",
        "torchdata==0.9.0",
        "scipy",
        "pyyaml"
    )
)   
"""
