"""Administrator accounts.

The admin role is granted to exactly these e-mail addresses. To add or remove
an administrator, edit this list and redeploy. The role is synchronised every
time the account signs in, so a change here applies to existing accounts too.
"""

from __future__ import annotations

ADMIN_EMAILS: frozenset[str] = frozenset({
    "sshreya.singh054@gmail.com",
    "saieshamittal.17@gmail.com",
    "aroravidhi342@gmail.com",
})

# Synthetic demo accounts keep the role they were generated with.
DEMO_DOMAIN_SUFFIX = "@demo.assembl.example"


def is_admin_email(email: str) -> bool:
    return email.strip().lower() in ADMIN_EMAILS


def role_for(email: str, current_role: str) -> str:
    """Role an account should have: admin iff listed above. A listed address is
    promoted; an admin no longer listed is demoted to student. Raters keep
    their role; synthetic demo accounts are left unchanged."""
    if email.endswith(DEMO_DOMAIN_SUFFIX):
        return current_role
    if is_admin_email(email):
        return "admin"
    return "student" if current_role == "admin" else current_role
