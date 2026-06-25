#!/usr/bin/env python3

import argparse
import os
import sys
from typing import Any

from pymisp import MISPUser, PyMISP


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a user in MISP with PyMISP.",
        epilog=(
            "Example: ./create_misp_user.py --user toto@truc.com "
            "--instance https://misp.local --api API_KEY --pwd 'Secret123!'"
        ),
    )
    parser.add_argument(
        "--user",
        required=True,
        help="User email to create in MISP.",
    )
    parser.add_argument(
        "--instance",
        required=True,
        help="MISP base URL, for example https://misp.local",
    )
    parser.add_argument(
        "--api",
        required=True,
        help="MISP API key with user creation permissions.",
    )
    parser.add_argument(
        "--pwd",
        required=True,
        help="Password for the new user.",
    )
    parser.add_argument(
        "--org-id",
        type=int,
        default=None,
        help="Target organisation ID. Defaults to MISP_ORG_ID or your own org_id.",
    )
    parser.add_argument(
        "--role-id",
        type=int,
        default=None,
        help="Target role ID. Defaults to MISP_ROLE_ID or the Org Admin role.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification.",
    )
    return parser


def resolve_org_id(misp: PyMISP, explicit_org_id: int | None) -> int:
    if explicit_org_id is not None:
        return explicit_org_id

    env_org_id = os.getenv("MISP_ORG_ID")
    if env_org_id:
        return int(env_org_id)

    organisations = misp.organisations(search="ORG_MAIN")
    organisation_items = (
        organisations.get("response", organisations)
        if isinstance(organisations, dict)
        else organisations
    )
    for organisation in organisation_items:
        organisation_data = organisation.get("Organisation", organisation)
        organisation_name = str(organisation_data.get("name", "")).strip()
        if organisation_name == "ORG_MAIN":
            return int(organisation_data["id"])

    me = misp.get_user("me")
    user_data = me.get("User", me)
    org_id = user_data.get("org_id")
    if org_id is None:
        raise RuntimeError(
            "Unable to resolve org_id automatically. Use --org-id or MISP_ORG_ID."
        )
    return int(org_id)


def resolve_role_id(misp: PyMISP, explicit_role_id: int | None) -> int:
    if explicit_role_id is not None:
        return explicit_role_id

    env_role_id = os.getenv("MISP_ROLE_ID")
    if env_role_id:
        return int(env_role_id)

    roles = misp.roles()
    role_items = roles.get("response", roles) if isinstance(roles, dict) else roles

    for role in role_items:
        role_data = role.get("Role", role)
        role_name = str(role_data.get("name", "")).strip().lower()
        if role_name == "org admin":
            return int(role_data["id"])

    for role in role_items:
        role_data = role.get("Role", role)
        default_role = role_data.get("default_role")
        if default_role in (True, 1, "1", "true", "True"):
            return int(role_data["id"])

    raise RuntimeError(
        "Unable to resolve role_id automatically. Use --role-id or MISP_ROLE_ID."
    )


def extract_user_payload(response: dict[str, Any]) -> dict[str, Any]:
    if "User" in response and isinstance(response["User"], dict):
        return response["User"]
    return response


def extract_error_payload_from_value(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, (list, tuple)):
        for item in reversed(value):
            payload = extract_error_payload_from_value(item)
            if payload is not None:
                return payload
    return None


def extract_error_payload(error: Exception) -> dict[str, Any] | None:
    for arg in reversed(error.args):
        payload = extract_error_payload_from_value(arg)
        if payload is not None:
            return payload
    return None


def is_duplicate_email_error(error_payload: dict[str, Any] | None) -> bool:
    if not error_payload:
        return False

    errors = error_payload.get("errors")
    if not isinstance(errors, dict):
        return False

    email_errors = errors.get("email")
    if isinstance(email_errors, list):
        return any("already exists" in str(message).lower() for message in email_errors)
    return "already exists" in str(email_errors).lower()


def find_user_by_email(misp: PyMISP, email: str) -> dict[str, Any] | None:
    users = misp.users(search=email)
    if isinstance(users, dict):
        return None

    for user in users:
        user_data = user.get("User", user) if isinstance(user, dict) else user
        if str(user_data.get("email", "")).strip().lower() == email.lower():
            return user_data
    return None


def main() -> int:
    args = build_parser().parse_args()
    misp = PyMISP(args.instance, args.api, ssl=not args.insecure)

    org_id = resolve_org_id(misp, args.org_id)
    role_id = resolve_role_id(misp, args.role_id)

    user = MISPUser()
    user.email = args.user
    user.password = args.pwd
    user.org_id = org_id
    user.role_id = role_id
    user.change_pw = False

    try:
        response = misp.add_user(user)
        if isinstance(response, dict) and response.get("errors"):
            error_payload = extract_error_payload_from_value(response["errors"])
            if not is_duplicate_email_error(error_payload):
                print(f"MISP error: {response['errors']}", file=sys.stderr)
                return 1
            response = None

        if response is not None:
            created_user = extract_user_payload(response)
            print("User created successfully")
            print(f"id={created_user.get('id', 'n/a')}")
            print(f"email={created_user.get('email', args.user)}")
            print(f"org_id={created_user.get('org_id', org_id)}")
            print(f"role_id={created_user.get('role_id', role_id)}")
            return 0
    except Exception as error:
        error_payload = extract_error_payload(error)
        if not is_duplicate_email_error(error_payload):
            print(f"MISP error: {error}", file=sys.stderr)
            return 1

    existing_user = find_user_by_email(misp, args.user)
    if existing_user is None:
        print(
            "User already exists, but it was not possible to retrieve it for password update.",
            file=sys.stderr,
        )
        return 1

    existing_user_id = existing_user.get("id")
    if existing_user_id is None:
        print("Existing user has no id; cannot update password.", file=sys.stderr)
        return 1

    updated_user = MISPUser()
    updated_user.email = str(existing_user.get("email", args.user))
    updated_user.password = args.pwd
    updated_user.org_id = int(existing_user.get("org_id", org_id))
    updated_user.role_id = int(existing_user.get("role_id", role_id))
    updated_user.change_pw = False
    if existing_user.get("disable"):
        updated_user.disable = existing_user["disable"]

    try:
        response = misp.update_user(updated_user, user_id=int(existing_user_id))
    except Exception as error:
        print(f"MISP error while updating existing user: {error}", file=sys.stderr)
        return 1

    if isinstance(response, dict) and response.get("errors"):
        print(
            f"MISP error while updating existing user: {response['errors']}",
            file=sys.stderr,
        )
        return 1

    updated_user_payload = extract_user_payload(response)
    print("User already existed; password updated successfully")
    print(f"id={updated_user_payload.get('id', existing_user_id)}")
    print(f"email={updated_user_payload.get('email', args.user)}")
    print(f"org_id={updated_user_payload.get('org_id', updated_user.org_id)}")
    print(f"role_id={updated_user_payload.get('role_id', updated_user.role_id)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
