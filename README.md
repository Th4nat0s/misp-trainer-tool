# mispcreate

Small PyMISP helpers for MISP training instances.

## Setup

Create a virtualenv and install dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Use an API key with permission to create users, create organisations, and add events.

If your MISP instance uses a self-signed certificate, add `--insecure`.

## Create one user

Create one user in an existing organisation:

```bash
.venv/bin/python create_misp_user.py \
  --api API_KEY \
  --instance https://dronetraining.training.misp-community.org \
  --user user1@org-admin.1.test \
  --pwd first-drone-forensic \
  --org-id 3
```

If `--org-id` is omitted, the script tries `MISP_ORG_ID`, then `ORG_MAIN`, then the API user's organisation.

Default role is `Org Admin`. Override with:

```bash
--role-id ROLE_ID
```

If the user already exists, the script updates the password.

## Create 30 users, one organisation per user

This creates/reuses `ORG_user1`, `ORG_user2`, ..., `ORG_user30`, then creates one user in each organisation:

```bash
.venv/bin/python reset.py \
  --api API_KEY \
  --instance https://dronetraining.training.misp-community.org \
  --pwd first-drone-forensic \
  --amount 30 \
  --prefix user \
  --create-orgs \
  --org-prefix ORG_
```

Generated emails:

```text
user1@org-admin.1.test
user2@org-admin.2.test
...
user30@org-admin.30.test
```

Generated organisations:

```text
ORG_user1
ORG_user2
...
ORG_user30
```

## Reset passwords for the 30 users

Run the same command with a new password. Existing users are detected and their password is updated:

```bash
.venv/bin/python reset.py \
  --api API_KEY \
  --instance https://dronetraining.training.misp-community.org \
  --pwd NEW_PASSWORD \
  --amount 30 \
  --prefix user \
  --create-orgs \
  --org-prefix ORG_
```

## Create or reset many users in one existing organisation

Use `--org-id` only when all users must belong to the same existing organisation:

```bash
.venv/bin/python reset.py \
  --api API_KEY \
  --instance https://dronetraining.training.misp-community.org \
  --pwd NEW_PASSWORD \
  --amount 30 \
  --prefix user \
  --org-id 3
```

`--org-id 3` is only an example. Use the real organisation ID from your MISP instance.

Do not use `--org-id` together with `--create-orgs`.

## Push event JSON files

Push all `*.json` event files from a folder:

```bash
.venv/bin/python pushjson.py \
  --key API_KEY \
  --url https://dronetraining.training.misp-community.org \
  --folder ./events
```

Each JSON file must be a MISP event export. The script continues after per-file errors and exits with `1` if any file failed.

## Development checks

Format and lint:

```bash
.venv/bin/black create_misp_user.py reset.py pushjson.py
.venv/bin/pylint create_misp_user.py reset.py pushjson.py
```

Syntax check:

```bash
.venv/bin/python -m py_compile create_misp_user.py reset.py pushjson.py
```
