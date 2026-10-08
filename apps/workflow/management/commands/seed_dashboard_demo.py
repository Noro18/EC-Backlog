"""Seed demo data so the dashboards can be inspected in a browser.

The real database has no document versions and no reviews yet, so every
requester widget renders zero. This command builds a small, fully worked
scenario instead of asking anyone to click through the whole flow.

It lives in `workflow` (not `backlog`) because it creates `DocumentVersion`
and `Review` records: `workflow` sits at the top of the dependency chain
(`workflow -> documents -> backlog -> accounts`), so it may touch every model.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.backlog.models import EC, Release
from apps.documents.models import DocumentVersion
from apps.workflow.models import Review

# One fixed password keeps the demo easy to remember. The command refuses to
# run outside DEBUG, so this never reaches a production database.
DEMO_PASSWORD = "DemoPass123!"

DEMO_USERS = [
    ("demo_req", "requester", "Demo Requester"),
    ("demo_req2", "requester", "Demo Requester 2"),
    ("demo_cd", "cd", "Demo CD"),
    ("demo_des", "des_team", "Demo DES"),
    ("demo_admin", "administrator", "Demo Admin"),
]

# What each of the requester's ECs should look like.
#   description, [(version_number, decision, comment), ...]
# `decision` is None while the CD has not decided yet.
REQUESTER_PLAN = [
    ("Draft: no document uploaded yet", []),
    ("Waiting for the CD", [("v1", None, "")]),
    ("Waiting for the CD", [("v1", None, "")]),
    ("Approved by the CD", [("v1", "approved", "Documento conforme.")]),
    (
        "Rejected once - needs a new version",
        [("v1", "rejected", "Falta a justificação do impacto.")],
    ),
    (
        "Rejected twice, third version waiting",
        [
            ("v1", "rejected", "Descrição incompleta."),
            ("v2", "rejected", "Falta o detalhe técnico."),
            ("v3", None, ""),
        ],
    ),
    (
        "Approved after a revision",
        [
            ("v1", "rejected", "Corrigir os exemplos."),
            ("v2", "approved", "OK, pode seguir."),
        ],
    ),
]

# Extra ECs assigned to the CD so their dashboard is not empty either.
# Their requester is a different user, which also proves the scoping works.
CD_QUEUE = ["Queue item for the CD review", "Another queue item", "Third queue item"]


class Command(BaseCommand):
    help = "Create demo users, ECs, document versions and reviews for the dashboards."

    def handle(self, *args, **options):
        # Never write demo rows into a real database.
        if not settings.DEBUG:
            raise CommandError("Refusing to seed demo data with DEBUG=False.")

        with transaction.atomic():
            users = self._ensure_users()
            release = self._release_with_room()

            created_ecs = self._seed_requester(users["demo_req"], users["demo_cd"], release)
            created_ecs += self._seed_cd_queue(users["demo_req2"], users["demo_cd"], release)

        self._summary(created_ecs)

    # ---------------------------------------------------------------- users

    def _ensure_users(self):
        User = get_user_model()
        users = {}
        for username, role, name in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@example.com", "name": name, "role": role},
            )
            if created:
                # set_password() hashes; assigning `password` directly would not.
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=["password"])
            elif user.role != role:
                raise CommandError(
                    f'User "{username}" already exists with role "{user.role}", expected "{role}".'
                )
            users[username] = user
        return users

    # ------------------------------------------------------------- releases

    def _release_with_room(self):
        """Reuse an open release with free capacity, or create one (rule: max 10 ECs)."""
        for release in Release.objects.filter(is_open=True).order_by("id"):
            if release.ec_count < release.capacity:
                return release

        year = timezone.localdate().year
        last = (
            Release.objects.filter(year=year).order_by("-number_sequence")
            .values_list("number_sequence", flat=True)
            .first()
        )
        sequence = (last or 0) + 1
        return Release.objects.create(
            year=year,
            number_sequence=sequence,
            release_code=f"TT_ON_{year}-{sequence:03d}",
            capacity=10,
            is_open=True,
        )

    # ------------------------------------------------------------------ ECS

    @staticmethod
    def _next_ec(year):
        """Return `(sequence, reference)` for a free EC id (RF01: never collide)."""
        last = (
            EC.objects.filter(year=year)
            .order_by("-number_sequence")
            .values_list("number_sequence", flat=True)
            .first()
        )
        sequence = (last or 0) + 1
        return sequence, f"CR{year}{sequence:03d}"

    def _seed_requester(self, requester, cd, release):
        created = []
        year = timezone.localdate().year
        base_date = timezone.localdate() - timedelta(days=len(REQUESTER_PLAN))

        for offset, (description, versions) in enumerate(REQUESTER_PLAN):
            sequence, reference = self._next_ec(year)
            # An EC without a document is still a draft, so it is not assigned
            # to a CD yet (RF07 says assignment happens after the upload).
            has_document = bool(versions)
            ec = EC.objects.create(
                year=year,
                number_sequence=sequence,
                reference=reference,
                description=description,
                requester=requester,
                responsible_cd=cd if has_document else None,
                release=release,
                creation_date=base_date + timedelta(days=offset),
            )
            self._seed_versions(ec, versions, cd)
            created.append(ec)

        return created

    def _seed_cd_queue(self, requester, cd, release):
        """Three ECs waiting on this CD, so `demo_cd` sees a non-empty queue."""
        created = []
        year = timezone.localdate().year

        for description in CD_QUEUE:
            sequence, reference = self._next_ec(year)
            ec = EC.objects.create(
                year=year,
                number_sequence=sequence,
                reference=reference,
                description=description,
                requester=requester,
                responsible_cd=cd,
                release=release,
                creation_date=timezone.localdate(),
            )
            # A version with no review is exactly what "pending decision" means.
            self._seed_versions(ec, [("v1", None, "")], cd)
            created.append(ec)

        return created

    @staticmethod
    def _seed_versions(ec, versions, cd):
        """Upload each version, then record the CD decision for it (RF05/RF09)."""
        for version_number, decision, comment in versions:
            version = DocumentVersion.objects.create(
                ec=ec,
                version_number=version_number,
                # The path is enough for the dashboard: it never serves the file.
                file="documents/demo.pdf",
                uploaded_by=ec.requester,
                change_reason=comment if decision == "rejected" else "",
            )
            if decision is None:
                continue
            # A rejection requires a comment, enforced by a DB check constraint.
            Review.objects.create(
                document_version=version,
                cd=cd,
                decision=decision,
                comment=comment,
            )

    # -------------------------------------------------------------- summary

    def _summary(self, created_ecs):
        """Print what was created and how to inspect it in the browser."""
        versions = DocumentVersion.objects.count()
        reviews = Review.objects.count()

        self.stdout.write(self.style.SUCCESS(f"\nSeeded {len(created_ecs)} ECs."))
        self.stdout.write(f"Document versions: {versions} | Reviews: {reviews}\n")

        self.stdout.write("Sign in with any of these:\n")
        for username, role, _name in DEMO_USERS:
            self.stdout.write(f"  {username:<12} {DEMO_PASSWORD:<14} role={role}")

        self.stdout.write("\nOpen /dashboard/ as demo_req and check the requester widgets:")
        self.stdout.write("  draft=1  submitted=3  approved=2  rejected=1")
        self.stdout.write("  versions per document: one EC with 3, one with 2, four with 1")
