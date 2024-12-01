import hashlib
import re

def generate_unique_id(text: str) -> str:
    normalized_text = re.sub(r'\W+', '', text).lower()
    return hashlib.md5(normalized_text.encode('utf-8')).hexdigest()