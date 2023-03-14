from lambda_function import lambda_handler

if __name__ == '__main__':
    events = [
        {'path': '/hello-world', 'httpMethod': 'GET'},
        {'path': '/doi', 'httpMethod': 'POST'},
        {'path': '/route/we/do/not/support', 'httpMethod': 'GET'},
    ]
    context = None
    for event in events:
        try:
            print('Resp:', lambda_handler(event, context))
        except Exception as e:
            print(e)
        print('----------------------')
