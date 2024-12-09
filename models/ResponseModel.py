import json
import azure.functions as func

class ResponseModel(func.HttpResponse):
    def __init__(self, data, status_code=200):
        super().__init__(
            body=json.dumps(data),
            status_code=status_code,
            mimetype="application/json",
        )