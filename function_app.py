import azure.functions as func
from blueprints.process_training_data_func import bp
from blueprints.chat import chat_bp
from blueprints.auth import auth_bp
from blueprints.class_management import turmas_bp
from blueprints.dashboard import dashboard_bp
from blueprints.knowledge_files import files_bp

app = func.FunctionApp()

app.register_blueprint(chat_bp)
app.register_functions(bp)
app.register_blueprint(files_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(turmas_bp)
app.register_blueprint(dashboard_bp)