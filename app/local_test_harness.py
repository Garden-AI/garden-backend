from lambda_function import lambda_handler
import json

if __name__ == '__main__':
    upload_payload = json.dumps({"direction": "upload", "s3_path": "willengler@uchicago.edu/example-model/model.zip"})
    download_payload = json.dumps({"direction": "download", "s3_path": "willengler@uchicago.edu/example-model/model.zip"})
    invalid_upload_payload = json.dumps({"direction": "upload", "s3_path": "willengler@uchicago.edu/example-model/model.tar"})

    events = [
        {'path': '/hello-world', 'httpMethod': 'GET'},
        {'path': '/doi', 'httpMethod': 'POST'},
        {'path': '/route/we/do/not/support', 'httpMethod': 'GET'},
        {'path': '/presigned-url', 'httpMethod': 'POST', 'body': upload_payload},
        {'path': '/presigned-url', 'httpMethod': 'POST', 'body': download_payload},
        {'path': '/presigned-url', 'httpMethod': 'POST', 'body': invalid_upload_payload},
    ]
    context = None
    for event in events:
        try:
            print('Resp:', lambda_handler(event, context))
        except Exception as e:
            print(e)
        print('----------------------')
