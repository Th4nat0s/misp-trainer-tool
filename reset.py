#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create multiple MISP users by calling create_misp_user.py.",
        epilog=(
            "Example: ./reset.py --prefix user --pwd 'Secret123!' "
            "--api API_KEY --amount 5 --instance https://misp.local --org-id 42"
        ),
    )
    parser.add_argument("--prefix", required=True, help="User email prefix.")
    parser.add_argument("--pwd", required=True, help="Password for all created users.")
    parser.add_argument("--api", required=True, help="MISP API key.")
    parser.add_argument(
        "--amount",
        required=True,
        type=int,
        help="Number of users to create, from 1 to amount.",
    )
    parser.add_argument(
        "--org-id",
        type=int,
        default=None,
        help="Target organisation ID. Passed through to create_misp_user.py.",
    )
    parser.add_argument(
        "--instance",
        default=os.getenv("MISP_INSTANCE"),
        help="MISP base URL. Defaults to MISP_INSTANCE.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification.",
    )
    parser.add_argument(
        "--create-orgs",
        action="store_true",
        help="Create one organisation per user, named from the email username.",
    )
    parser.add_argument(
        "--org-prefix",
        default="",
        help="Prefix for organisation names created with --create-orgs.",
    )
    return parser


def build_email(prefix: str, index: int) -> str:
    return f"{prefix}{index}@org-admin.{index}.test"


def build_org_name(email: str, org_prefix: str) -> str:
    username = email.split("@", 1)[0]
    return f"{org_prefix}{username}"


def extract_organisation_payload(response: dict) -> dict:
    if "Organisation" in response and isinstance(response["Organisation"], dict):
        return response["Organisation"]
    return response


def find_organisation_by_name(misp, name: str) -> dict | None:
    organisations = misp.organisations(search=name)
    organisation_items = (
        organisations.get("response", organisations)
        if isinstance(organisations, dict)
        else organisations
    )

    for organisation in organisation_items:
        organisation_data = organisation.get("Organisation", organisation)
        if str(organisation_data.get("name", "")).strip() == name:
            return organisation_data
    return None


def create_or_get_organisation(misp, name: str) -> int:
    from pymisp import MISPOrganisation

    existing_organisation = find_organisation_by_name(misp, name)
    if existing_organisation is not None:
        return int(existing_organisation["id"])

    organisation = MISPOrganisation()
    organisation.name = name
    response = misp.add_organisation(organisation)
    if isinstance(response, dict) and response.get("errors"):
        raise RuntimeError(response["errors"])

    created_organisation = extract_organisation_payload(response)
    organisation_id = created_organisation.get("id")
    if organisation_id is None:
        raise RuntimeError(f"Created organisation has no id: {response}")
    return int(organisation_id)


def main() -> int:
    args = build_parser().parse_args()

    if args.amount < 1:
        print("--amount must be >= 1", file=sys.stderr)
        return 1

    if args.org_id is not None and args.create_orgs:
        print("--org-id cannot be used with --create-orgs", file=sys.stderr)
        return 1

    if not args.instance:
        print(
            "Missing MISP instance. Use --instance or set MISP_INSTANCE.",
            file=sys.stderr,
        )
        return 1

    script_path = Path(__file__).with_name("create_misp_user.py")
    if not script_path.exists():
        print(f"Missing helper script: {script_path}", file=sys.stderr)
        return 1

    misp = None
    if args.create_orgs:
        from pymisp import PyMISP

        misp = PyMISP(args.instance, args.api, ssl=not args.insecure)

    failures = 0

    for index in range(1, args.amount + 1):
        email = build_email(args.prefix, index)
        org_id = args.org_id

        if args.create_orgs:
            org_name = build_org_name(email, args.org_prefix)
            try:
                org_id = create_or_get_organisation(misp, org_name)
            except Exception as error:
                failures += 1
                print(
                    f"[{index}/{args.amount}] failed to create org {org_name}",
                    file=sys.stderr,
                )
                print(f"MISP error: {error}", file=sys.stderr)
                continue
            print(f"[{index}/{args.amount}] organisation {org_name} id={org_id}")

        command = [
            sys.executable,
            str(script_path),
            "--user",
            email,
            "--instance",
            args.instance,
            "--api",
            args.api,
            "--pwd",
            args.pwd,
        ]
        if org_id is not None:
            command.extend(["--org-id", str(org_id)])
        if args.insecure:
            command.append("--insecure")

        print(f"[{index}/{args.amount}] creating {email}")
        result = subprocess.run(command, capture_output=True, text=True, check=False)

        if result.returncode == 0:
            stdout = result.stdout.strip()
            if stdout:
                print(stdout)
            continue

        failures += 1
        print(f"[{index}/{args.amount}] failed for {email}", file=sys.stderr)
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        if stderr:
            print(stderr, file=sys.stderr)
        elif stdout:
            print(stdout, file=sys.stderr)

    if failures:
        print(f"Completed with {failures} failure(s).", file=sys.stderr)
        return 1

    print(f"Created {args.amount} user(s) successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
