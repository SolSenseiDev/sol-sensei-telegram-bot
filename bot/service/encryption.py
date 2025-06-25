from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("ENCRYPTION_KEY")
if not key:
    raise ValueError("❌ ENCRYPTION_KEY is missing!")

fernet = Fernet(key)


def encrypt_seed(seed: str) -> str:
    return fernet.encrypt(seed.encode()).decode()


def decrypt_seed(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()