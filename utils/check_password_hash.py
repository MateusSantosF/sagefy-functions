import bcrypt

def check_password_hash(stored_hash: str | None, password: str) -> bool:
    """
    Verifica se a senha fornecida corresponde ao hash armazenado.
    
    :param stored_hash: Hash da senha armazenado.
    :param password: Senha em texto plano a ser verificada.
    :return: True se corresponder, False caso contrário.
    """

    if stored_hash is None:
        return False
    # Codifica a senha e o hash armazenado para bytes
    password_bytes = password.encode('utf-8')
    stored_hash_bytes = stored_hash.encode('utf-8')
    
    # Usa bcrypt para verificar a correspondência
    return bcrypt.checkpw(password_bytes, stored_hash_bytes)
