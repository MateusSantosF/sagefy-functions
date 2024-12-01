import azure.functions as func
from blueprints.process_training_data_func import bp
from blueprints.chat import chat_bp

app = func.FunctionApp()

app.register_blueprint(chat_bp)
app.register_functions(bp)
