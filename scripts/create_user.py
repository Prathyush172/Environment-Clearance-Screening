"""Script to create development or administrative user accounts."""

import sys
import os
import uuid
import asyncio
import argparse

sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import select

from libs.common.db.session import get_db_session, init_db
from libs.common.db.models import User
from services.api.auth import hash_password


async def create_user(
    email: str,
    username: str,
    password: str,
    role: str = "user",
    client_id: str = None,
    full_name: str = None,
) -> User:
    await init_db()
    async with get_db_session() as session:
        # Check if already exists
        q = select(User).where((User.username == username) | (User.email == email.lower()))
        res = await session.execute(q)
        existing = res.scalar_one_or_none()
        if existing:
            print(f"[!] User '{username}' or email '{email}' already exists (ID: {existing.id}, Role: {existing.role}).")
            # Update password if requested
            existing.hashed_password = hash_password(password)
            existing.role = role
            if client_id:
                existing.client_id = client_id
            session.add(existing)
            print(f"[+] Updated user '{username}' credentials.")
            return existing

        user_id = str(uuid.uuid4())
        cid = client_id or f"client_{username}"
        fname = full_name or username
        new_user = User(
            id=user_id,
            email=email.lower().strip(),
            username=username.strip(),
            hashed_password=hash_password(password),
            full_name=fname,
            role=role,
            client_id=cid,
            is_active=True,
        )
        session.add(new_user)
        print(f"[+] Created user '{username}' ({email}) with role '{role}' and client_id '{cid}'.")
        return new_user


async def seed_dev_users():
    """Seed default development accounts if not in production."""
    dev_users = [
        {
            "email": "admin@eia.gov.in",
            "username": "admin",
            "password": "AdminPass123!",
            "role": "admin",
            "client_id": "client_admin",
            "full_name": "MoEFCC System Administrator",
        },
        {
            "email": "officer@eia.gov.in",
            "username": "officer",
            "password": "OfficerPass123!",
            "role": "user",
            "client_id": "client_officer",
            "full_name": "EIA Screening Officer",
        },
        {
            "email": "user2@eia.gov.in",
            "username": "user2",
            "password": "User2Pass123!",
            "role": "user",
            "client_id": "client_user2",
            "full_name": "External Project Proponent",
        },
    ]
    print("[*] Seeding development accounts...")
    for u in dev_users:
        await create_user(**u)
    print("[*] Dev seed complete.")


def main():
    parser = argparse.ArgumentParser(description="Manage EIA Pre-Screening user accounts.")
    parser.add_argument("--email", type=str, help="User email address")
    parser.add_argument("--username", type=str, help="Username")
    parser.add_argument("--password", type=str, help="Plaintext password to hash")
    parser.add_argument("--role", type=str, default="user", choices=["user", "admin", "auditor"], help="User role")
    parser.add_argument("--client-id", type=str, default=None, help="Tenant or client ID")
    parser.add_argument("--full-name", type=str, default=None, help="Full name")
    parser.add_argument("--dev-seed", action="store_true", help="Seed standard development users")

    args = parser.parse_args()

    if args.dev_seed:
        asyncio.run(seed_dev_users())
    elif args.email and args.username and args.password:
        asyncio.run(
            create_user(
                email=args.email,
                username=args.username,
                password=args.password,
                role=args.role,
                client_id=args.client_id,
                full_name=args.full_name,
            )
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
