import azure.functions as func
from blueprints.process_training_data_func import bp

app = func.FunctionApp()

app.register_functions(bp)
