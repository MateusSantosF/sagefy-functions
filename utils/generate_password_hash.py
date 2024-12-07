import bcrypt


def generate_password_hash(password: str) -> str:
    """
    Gera um hash seguro para a senha fornecida usando bcrypt.
    
    :param password: Senha em texto plano.
    :return: Hash da senha como string.
    """
    # Gera o hash da senha. O bcrypt automaticamente gera um salt.
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    # Retorna o hash decodificado para string
    return hashed.decode('utf-8')
