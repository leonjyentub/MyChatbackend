import os
from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    Date,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    insert,
    or_,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError


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


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


database_url = os.getenv("DATABASE_URL")
engine = create_engine(normalize_database_url(database_url)) if database_url else None
metadata = MetaData()

users_table = Table(
    "users",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("username", String(30), nullable=False, unique=True, index=True),
    Column("password", String(60), nullable=False),
    Column("name", String(40), nullable=False),
    Column("birthday", Date, nullable=True),
    Column("avatar_url", String, nullable=True),
    Column("created_at", String, nullable=False),
)

friendships_table = Table(
    "friendships",
    metadata,
    Column("user_a", String(32), primary_key=True),
    Column("user_b", String(32), primary_key=True),
)

messages_table = Table(
    "messages",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("sender_id", String(32), nullable=False, index=True),
    Column("receiver_id", String(32), nullable=False, index=True),
    Column("text", String(1000), nullable=False),
    Column("created_at", String, nullable=False),
)


@app.on_event("startup")
def create_database_tables() -> None:
    if engine:
        metadata.create_all(engine)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_user(user: dict) -> dict:
    birthday = user.get("birthday")
    return {
        "id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "birthday": birthday.isoformat() if isinstance(birthday, date) else birthday,
        "avatar_url": user.get("avatar_url"),
        "created_at": user["created_at"],
    }


def find_user(user_id: str) -> dict:
    if engine:
        with engine.begin() as conn:
            row = (
                conn.execute(select(users_table).where(users_table.c.id == user_id))
                .mappings()
                .first()
            )
        if row:
            return dict(row)
        raise HTTPException(status_code=404, detail="User not found")

    for user in users:
        if user["id"] == user_id:
            return user
    raise HTTPException(status_code=404, detail="User not found")


def find_user_by_username(username: str) -> Optional[dict]:
    if engine:
        with engine.begin() as conn:
            row = (
                conn.execute(
                    select(users_table).where(users_table.c.username == username)
                )
                .mappings()
                .first()
            )
        return dict(row) if row else None

    for user in users:
        if user["username"] == username:
            return user
    return None


def friendship_key(user_a: str, user_b: str) -> tuple[str, str]:
    return tuple(sorted([user_a, user_b]))


def ensure_friends(user_a: str, user_b: str) -> None:
    if engine:
        key_a, key_b = friendship_key(user_a, user_b)
        with engine.begin() as conn:
            row = conn.execute(
                select(friendships_table).where(
                    friendships_table.c.user_a == key_a,
                    friendships_table.c.user_b == key_b,
                )
            ).first()
        if not row:
            raise HTTPException(status_code=403, detail="Users are not friends")
        return

    if friendship_key(user_a, user_b) not in friendships:
        raise HTTPException(status_code=403, detail="Users are not friends")


def message_between(user_a: str, user_b: str) -> list[dict]:
    if engine:
        with engine.begin() as conn:
            rows = conn.execute(
                select(messages_table).where(
                    or_(
                        (messages_table.c.sender_id == user_a)
                        & (messages_table.c.receiver_id == user_b),
                        (messages_table.c.sender_id == user_b)
                        & (messages_table.c.receiver_id == user_a),
                    )
                )
            ).mappings().all()
        return [dict(row) for row in rows]

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
    user = {
        "id": uuid4().hex[:8],
        "username": payload.username,
        "password": payload.password,
        "name": payload.display_name or payload.username,
        "birthday": None,
        "avatar_url": None,
        "created_at": now_iso(),
    }
    if engine:
        try:
            with engine.begin() as conn:
                conn.execute(insert(users_table).values(**user))
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Username already exists") from None
        return public_user(user)

    if find_user_by_username(payload.username):
        raise HTTPException(status_code=409, detail="Username already exists")

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
    changes = {
        "name": payload.name,
        "birthday": payload.birthday,
        "avatar_url": payload.avatar_url,
    }
    if engine:
        with engine.begin() as conn:
            conn.execute(update(users_table).where(users_table.c.id == user_id).values(**changes))
        return public_user({**user, **changes})

    user["name"] = changes["name"]
    user["birthday"] = payload.birthday.isoformat() if payload.birthday else None
    user["avatar_url"] = changes["avatar_url"]
    return public_user(user)


@app.get("/users/{user_id}/friends")
def get_friends(user_id: str):
    find_user(user_id)
    if engine:
        with engine.begin() as conn:
            rows = conn.execute(
                select(friendships_table).where(
                    or_(friendships_table.c.user_a == user_id, friendships_table.c.user_b == user_id)
                )
            ).mappings().all()
        friend_ids = [
            row["user_b"] if row["user_a"] == user_id else row["user_a"]
            for row in rows
        ]
        return [public_user(find_user(friend_id)) for friend_id in friend_ids]

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

    if engine:
        key_a, key_b = friendship_key(user_id, payload.friend_id)
        with engine.begin() as conn:
            conn.execute(
                delete(friendships_table).where(
                    friendships_table.c.user_a == key_a,
                    friendships_table.c.user_b == key_b,
                )
            )
            conn.execute(insert(friendships_table).values(user_a=key_a, user_b=key_b))
        return {"message": "Friend added"}

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
    if engine:
        with engine.begin() as conn:
            conn.execute(insert(messages_table).values(**message))
        return message

    messages.append(message)
    return message


@app.get("/dev/seed")
@app.post("/dev/seed")
def seed_data():
    if engine:
        with engine.begin() as conn:
            existing_user = conn.execute(select(users_table.c.id).limit(1)).first()
        if existing_user:
            return {"message": "Seed data already exists"}
    elif users:
        return {"message": "Seed data already exists"}

    alice = {
        "id": "alice001",
        "username": "alice",
        "password": "1234",
        "name": "Alice",
        "birthday": date(2001, 1, 1),
        "avatar_url": "https://i.pravatar.cc/150?img=1",
        "created_at": now_iso(),
    }
    bob = {
        "id": "bob002",
        "username": "bob",
        "password": "1234",
        "name": "Bob",
        "birthday": date(2002, 2, 2),
        "avatar_url": "https://i.pravatar.cc/150?img=2",
        "created_at": now_iso(),
    }
    message = {
        "id": uuid4().hex,
        "sender_id": bob["id"],
        "receiver_id": alice["id"],
        "text": "Hello Alice, this is a sample message.",
        "created_at": now_iso(),
    }
    if engine:
        key_a, key_b = friendship_key(alice["id"], bob["id"])
        with engine.begin() as conn:
            conn.execute(insert(users_table), [alice, bob])
            conn.execute(insert(friendships_table).values(user_a=key_a, user_b=key_b))
            conn.execute(insert(messages_table).values(**message))
    else:
        users.extend([alice, bob])
        friendships.add(friendship_key(alice["id"], bob["id"]))
        messages.append(message)
    return {"message": "Seed data created", "users": [public_user(alice), public_user(bob)]}
