"""
Authentication module — Username + Password lokal
Hash: SHA256 + salt sederhana
Storage: data/users.json (local) or Supabase (cloud)
"""
import os, json, hashlib, threading, time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
USERS_FILE = DATA_DIR / "users.json"

os.makedirs(DATA_DIR, exist_ok=True)

_lock = threading.Lock()


def _load_users() -> dict:
    """Load users from JSON file."""
    if not USERS_FILE.exists():
        return {}
    try:
        with open(USERS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_users(users: dict):
    """Save users to JSON file."""
    with _lock:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)


def _hash_password(password: str, salt: str = "") -> str:
    """Hash password with SHA256 + salt."""
    return hashlib.sha256((password + salt).encode()).hexdigest()


def _generate_salt() -> str:
    """Generate a random salt."""
    return hashlib.sha256(str(time.time()).encode() + os.urandom(8)).hexdigest()[:16]


def register(username: str, password: str) -> tuple[bool, str]:
    """
    Register a new user.
    Returns (success, message).
    """
    username = username.strip().lower()
    if not username:
        return False, "Username tidak boleh kosong."
    if len(username) < 3:
        return False, "Username minimal 3 karakter."
    if len(password) < 4:
        return False, "Password minimal 4 karakter."

    users = _load_users()
    if username in users:
        return False, f"Username '{username}' sudah terdaftar."

    salt = _generate_salt()
    users[username] = {
        "password": _hash_password(password, salt),
        "salt": salt,
        "name": username,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_login": "",
    }
    _save_users(users)
    return True, f"Registrasi berhasil! Silakan login."


def login(username: str, password: str) -> tuple[bool, str, dict]:
    """
    Verify username and password.
    Returns (success, message, user_data).
    """
    username = username.strip().lower()
    if not username or not password:
        return False, "Username dan password harus diisi.", {}

    users = _load_users()
    user = users.get(username)

    if not user:
        return False, "Username atau password salah.", {}

    hashed = _hash_password(password, user["salt"])
    if hashed != user["password"]:
        return False, "Username atau password salah.", {}

    # Update last login
    user["last_login"] = time.strftime("%Y-%m-%d %H:%M:%S")
    users[username] = user
    _save_users(users)

    return True, "Login berhasil!", {
        "id": username,
        "name": user.get("name", username),
        "email": "",
        "avatar": "",
    }


def list_users() -> list[str]:
    """List all registered usernames (for admin)."""
    users = _load_users()
    return list(users.keys())


def user_exists(username: str) -> bool:
    """Check if username exists."""
    users = _load_users()
    return username.strip().lower() in users


def change_password(username: str, old_password: str, new_password: str) -> tuple[bool, str]:
    """Change password for existing user."""
    username = username.strip().lower()
    if len(new_password) < 4:
        return False, "Password baru minimal 4 karakter."

    users = _load_users()
    user = users.get(username)
    if not user:
        return False, "User tidak ditemukan."

    hashed = _hash_password(old_password, user["salt"])
    if hashed != user["password"]:
        return False, "Password lama salah."

    user["salt"] = _generate_salt()
    user["password"] = _hash_password(new_password, user["salt"])
    users[username] = user
    _save_users(users)
    return True, "Password berhasil diubah."
