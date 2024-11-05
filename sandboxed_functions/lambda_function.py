def write_to_tmp_file(file_contents: str):
    import tempfile

    tmp_file_path = tempfile.mktemp() + ".py"
    with open(tmp_file_path, "w") as f:
        f.write(file_contents)
    return tmp_file_path


def get_app_from_file_contents(file_contents: str):
    from modal.cli.import_refs import import_app

    tmp_file_path = write_to_tmp_file(file_contents)

    try:
        user_app = import_app(tmp_file_path)
    except Exception as e:
        # TODO: identify failure modes and propagate those back
        raise e

    return user_app


def validate_modal_file(file_contents: str):
    user_app = get_app_from_file_contents(file_contents)
    function_names = [f for f in user_app.registered_functions if "*" not in f]
    app_name = user_app.name
    return {"function_names": function_names, "app_name": app_name}

    # TODO: confirm nothing dastardly on the app/functions


def deploy_modal_app(
    file_contents: str, app_name: str, token_id: str, token_secret: str, env: str
):
    from modal import enable_output
    from modal.cli.run import deploy_app, ensure_env
    from modal.client import Client
    import os

    clean_dir = "/tmp/modal_deploy"
    os.makedirs(clean_dir, exist_ok=True)
    original_dir = os.getcwd()
    os.chdir(clean_dir)

    try:
        with enable_output():
            ensure_env(env)
            app = get_app_from_file_contents(file_contents)
            client = Client.from_credentials(token_id, token_secret)
            res = deploy_app(app, name=app_name, client=client, environment_name=env)
    finally:
        os.chdir(original_dir)

    return res.app_id


def lambda_handler(event, context):
    fn_name = event["fn_name"]
    payload = event["payload"]
    if fn_name == "deploy_modal_app":
        file_contents = payload["file_contents"]
        app_name = payload["app_name"]
        token_id = payload["token_id"]
        token_secret = payload["token_secret"]
        env = payload["env"]
        return deploy_modal_app(file_contents, app_name, token_id, token_secret, env)
    elif fn_name == "validate_modal_file":
        file_contents = payload["file_contents"]
        return validate_modal_file(file_contents)
