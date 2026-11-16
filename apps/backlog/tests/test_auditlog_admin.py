"""Tests for the custom ``LogEntryAdmin`` (spec ``.opencode/specs/AUDITLOG_ADMIN.md``)."""

import pytest
from auditlog.models import LogEntry
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.accounts.models import User
from apps.backlog.models import EC
from apps.backlog.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

LOGENTRY_LIST_URL = "/admin/auditlog/logentry/"


def model_admin():
    return admin.site._registry[LogEntry]


def make_entry(
    *,
    actor=None,
    action=LogEntry.Action.UPDATE,
    changes=None,
    object_repr="2026-011",
    content_type=None,
):
    if content_type is None:
        content_type = ContentType.objects.get_for_model(EC)
    return LogEntry.objects.create(
        content_type=content_type,
        object_pk="1",
        object_id=1,
        object_repr=object_repr,
        action=action,
        changes=changes,
        actor=actor,
    )


class TestLogEntryAdminRegistration:
    def test_logentry_admin_is_registered(self, admin_client):
        registered = admin.site._registry[LogEntry]
        assert registered.__class__.__module__ == "apps.backlog.admin"
        assert registered.__class__.__name__ == "LogEntryAdmin"

        response = admin_client.get(LOGENTRY_LIST_URL)
        assert response.status_code == 200
        html = response.content.decode()
        for header in ("Created", "Actor", "Aksi", "Objek", "Perubahan"):
            assert header in html

    def test_no_add_change_delete_permissions(self, rf):
        ma = model_admin()
        request = rf.get(LOGENTRY_LIST_URL)

        assert ma.has_add_permission(request) is False
        assert ma.has_change_permission(request) is False
        assert ma.has_delete_permission(request) is False


class TestActorColumn:
    def test_actor_column_shows_full_name(self):
        user = UserFactory(name="Maria da Costa")
        entry = make_entry(actor=user)

        assert model_admin().actor_name(entry) == "Maria da Costa"

    def test_created_column_uses_dd_mon_yyyy(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        entry = make_entry()
        LogEntry.objects.filter(pk=entry.pk).update(
            timestamp=datetime(2026, 4, 18, 8, 15, tzinfo=ZoneInfo("Asia/Dili"))
        )
        entry.refresh_from_db()

        assert model_admin().created(entry) == "18-Apr-2026 08:15"

    def test_actor_column_falls_back_to_username(self):
        user = UserFactory(name="", first_name="", last_name="")
        entry = make_entry(actor=user)

        assert model_admin().actor_name(entry) == user.username

    def test_actor_none_renders_sistema(self):
        entry = make_entry(actor=None)

        assert model_admin().actor_name(entry) == "Sistema"


class TestActionBadge:
    @pytest.mark.parametrize(
        ("action", "label", "color"),
        [
            (LogEntry.Action.CREATE, "Dibuat", "#198754"),
            (LogEntry.Action.UPDATE, "Diperbarui", "#0d6efd"),
            (LogEntry.Action.DELETE, "Dihapus", "#dc3545"),
            (LogEntry.Action.ACCESS, "access", "#6c757d"),
        ],
    )
    def test_action_badge_renders_portuguese_label(self, action, label, color):
        entry = make_entry(action=action)

        html = str(model_admin().action_badge(entry))

        assert label in html
        assert color in html


class TestChangesSummary:
    def test_changes_summary_renders_status_arrow(self):
        entry = make_entry(changes={"status": ["in_validation", "approved"]})

        assert model_admin().changes_summary(entry) == "status: Em validação → Aprovada"

    def test_changes_summary_renders_multiple_fields(self):
        entry = make_entry(
            changes={
                "status": ["in_validation", "approved"],
                "decision": ["None", "approved"],
            }
        )

        assert (
            model_admin().changes_summary(entry)
            == "status: Em validação → Aprovada; decision: approved"
        )

    def test_changes_none_renders_dash(self):
        entry = make_entry(changes=None)

        assert model_admin().changes_summary(entry) == "-"

    def test_changes_summary_skips_empty_comment(self):
        # Real review CREATE rows store comment as ["None", ""].
        entry = make_entry(
            changes={"comment": ["None", ""], "decision": ["None", "approved"]}
        )

        assert model_admin().changes_summary(entry) == "decision: approved"

    def test_changes_summary_marks_filled_comment(self):
        entry = make_entry(changes={"comment": ["None", "hadia o número 2"]})

        assert model_admin().changes_summary(entry) == "comment: (baru diisi)"

    def test_changes_summary_truncates_long_text(self):
        entry = make_entry(changes={"description": ["old", "x" * 400]})

        summary = model_admin().changes_summary(entry)

        assert len(summary) <= 200
        assert summary.endswith("…")


class TestObjectLink:
    def test_object_link_renders_ec_code(self):
        entry = make_entry(object_repr="2026-011")

        html = str(model_admin().object_link(entry))

        assert "EC 2026-011" in html
        url = reverse("admin:backlog_ec_change", args=[entry.object_pk])
        assert f'href="{url}"' in html

    def test_object_link_prefixes_plain_user_repr(self):
        user_ct = ContentType.objects.get_for_model(User)
        entry = make_entry(object_repr="pualuan", content_type=user_ct)

        html = str(model_admin().object_link(entry))

        assert "User pualuan" in html

    def test_object_link_without_content_type_renders_plain_text(self):
        entry = LogEntry(
            object_repr="2026-011",
            object_pk="1",
            action=LogEntry.Action.UPDATE,
        )

        assert model_admin().object_link(entry) == "2026-011"
