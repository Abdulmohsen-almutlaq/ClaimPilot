from dataclasses import dataclass
from typing import Literal

from app.auth.security import hash_password

Role = Literal["submitter", "approver", "admin"]


@dataclass(frozen=True)
class User:
    email: str
    password_hash: str
    role: Role


_SEED_USERS: dict[str, User] = {
    "submitter@demo.io": User("submitter@demo.io", hash_password("demo"), "submitter"),
    "approver@demo.io": User("approver@demo.io", hash_password("demo"), "approver"),
    "admin@demo.io": User("admin@demo.io", hash_password("demo"), "admin"),
}


def get_user(email: str) -> User | None:
    return _SEED_USERS.get(email)
