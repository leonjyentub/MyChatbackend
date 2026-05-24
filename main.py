from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="Teaching Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=4, max_length=60)
    display_name: Optional[str] = Field(default=None, max_length=40)


class LoginRequest(BaseModel):
    username: str
    password: str


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    birthday: Optional[date] = None
    avatar_url: Optional[str] = None


class AddFriendRequest(BaseModel):
    friend_id: str


class MessageCreate(BaseModel):
    sender_id: str
    text: str = Field(min_length=1, max_length=1000)


users: list[dict] = []
friendships: set[tuple[str, str]] = set()
messages: list[dict] = []


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "birthday": user.get("birthday"),
        "avatar_url": user.get("avatar_url"),
        "created_at": user["created_at"],
    }


def find_user(user_id: str) -> dict:
    for user in users:
        if user["id"] == user_id:
            return user
    raise HTTPException(status_code=404, detail="User not found")


def find_user_by_username(username: str) -> Optional[dict]:
    for user in users:
        if user["username"] == username:
            return user
    return None


def friendship_key(user_a: str, user_b: str) -> tuple[str, str]:
    return tuple(sorted([user_a, user_b]))


def ensure_friends(user_a: str, user_b: str) -> None:
    if friendship_key(user_a, user_b) not in friendships:
        raise HTTPException(status_code=403, detail="Users are not friends")


def message_between(user_a: str, user_b: str) -> list[dict]:
    return [
        message
        for message in messages
        if {message["sender_id"], message["receiver_id"]} == {user_a, user_b}
    ]


@app.get("/")
def root():
    return {"message": "Chat API is running"}


@app.post("/auth/register")
def register(payload: RegisterRequest):
    if find_user_by_username(payload.username):
        raise HTTPException(status_code=409, detail="Username already exists")

    user = {
        "id": uuid4().hex[:8],
        "username": payload.username,
        "password": payload.password,
        "name": payload.display_name or payload.username,
        "birthday": None,
        "avatar_url": None,
        "created_at": now_iso(),
    }
    users.append(user)
    return public_user(user)


@app.post("/auth/login")
def login(payload: LoginRequest):
    user = find_user_by_username(payload.username)
    if not user or user["password"] != payload.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return public_user(user)


@app.get("/users/{user_id}")
def get_user(user_id: str):
    return public_user(find_user(user_id))


@app.put("/users/{user_id}")
def update_profile(user_id: str, payload: ProfileUpdate):
    user = find_user(user_id)
    user["name"] = payload.name
    user["birthday"] = payload.birthday.isoformat() if payload.birthday else None
    user["avatar_url"] = payload.avatar_url
    return public_user(user)


@app.get("/users/{user_id}/friends")
def get_friends(user_id: str):
    find_user(user_id)
    friend_ids = [
        key[1] if key[0] == user_id else key[0]
        for key in friendships
        if user_id in key
    ]
    return [public_user(find_user(friend_id)) for friend_id in friend_ids]


@app.post("/users/{user_id}/friends")
def add_friend(user_id: str, payload: AddFriendRequest):
    find_user(user_id)
    find_user(payload.friend_id)
    if user_id == payload.friend_id:
        raise HTTPException(status_code=400, detail="Cannot add yourself")

    friendships.add(friendship_key(user_id, payload.friend_id))
    return {"message": "Friend added"}


@app.get("/users/{user_id}/chats")
def get_chats(user_id: str):
    find_user(user_id)
    chats = []
    for friend in get_friends(user_id):
        chat_messages = message_between(user_id, friend["id"])
        latest = max(chat_messages, key=lambda item: item["created_at"]) if chat_messages else None
        chats.append(
            {
                "friend": friend,
                "last_message": latest,
                "last_time": latest["created_at"] if latest else None,
            }
        )

    return sorted(chats, key=lambda item: item["last_time"] or "", reverse=True)


@app.get("/chats/{user_id}/{friend_id}/messages")
def get_messages(user_id: str, friend_id: str):
    find_user(user_id)
    find_user(friend_id)
    ensure_friends(user_id, friend_id)
    return sorted(message_between(user_id, friend_id), key=lambda item: item["created_at"])


@app.post("/chats/{user_id}/{friend_id}/messages")
def send_message(user_id: str, friend_id: str, payload: MessageCreate):
    find_user(user_id)
    find_user(friend_id)
    ensure_friends(user_id, friend_id)
    if payload.sender_id != user_id:
        raise HTTPException(status_code=400, detail="Sender must match current user")

    message = {
        "id": uuid4().hex,
        "sender_id": user_id,
        "receiver_id": friend_id,
        "text": payload.text,
        "created_at": now_iso(),
    }
    messages.append(message)
    return message


@app.get("/dev/seed")
@app.post("/dev/seed")
def seed_data():
    if users:
        return {"message": "Seed data already exists"}

    alice = {
        "id": "alice001",
        "username": "alice",
        "password": "1234",
        "name": "Alice",
        "birthday": "2001-01-01",
        "avatar_url": "https://i.pravatar.cc/150?img=1",
        "created_at": now_iso(),
    }
    bob = {
        "id": "bob002",
        "username": "bob",
        "password": "1234",
        "name": "Bob",
        "birthday": "2002-02-02",
        "avatar_url": "https://i.pravatar.cc/150?img=2",
        "created_at": now_iso(),
    }
    users.extend([alice, bob])
    friendships.add(friendship_key(alice["id"], bob["id"]))
    messages.append(
        {
            "id": uuid4().hex,
            "sender_id": bob["id"],
            "receiver_id": alice["id"],
            "text": "Hello Alice, this is a sample message.",
            "created_at": now_iso(),
        }
    )
    return {"message": "Seed data created", "users": [public_user(alice), public_user(bob)]}
