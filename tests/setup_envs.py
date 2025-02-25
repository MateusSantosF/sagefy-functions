import json
import os


def load_local_settings():
    """Carrega variáveis de ambiente do local.settings.json para testes"""
    settings_path = os.path.join(os.path.dirname(__file__), "../local.settings.json")

    if not os.path.exists(settings_path):
        raise FileNotFoundError(f"Arquivo local.settings.json não encontrado: {settings_path}")

    with open(settings_path, "r") as f:
        settings = json.load(f)

    for key, value in settings.get("Values", {}).items():
        os.environ[key] = value  # Define as variáveis de ambiente

# Carrega as variáveis antes de tudo
load_local_settings()