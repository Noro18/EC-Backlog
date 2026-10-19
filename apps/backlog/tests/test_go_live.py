from datetime import date

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.accounts.models import User
from apps.backlog.services import record_go_live
from apps.backlog.tests.factories import ReleaseFactory, UserFactory

pytestmark = pytest.mark.django_db

GO_LIVE = date(2026, 12, 1)


def _closed_release():
    release = ReleaseFactory(is_open=False)
    return release


class TestRecordGoLive:
    def test_requester_saves_date(self):
        release = _closed_release()
        requester = UserFactory(role=User.Role.REQUESTER)

        result = record_go_live(release, requester, GO_LIVE)

        assert result.production_go_live_date == GO_LIVE

    def test_open_release_refused(self):
        release = ReleaseFactory(is_open=True)
        requester = UserFactory(role=User.Role.REQUESTER)

        with pytest.raises(ValidationError):
            record_go_live(release, requester, GO_LIVE)

        release.refresh_from_db()
        assert release.production_go_live_date is None

    def test_non_requester_refused(self):
        release = _closed_release()
        cd = UserFactory(role=User.Role.CD)

        with pytest.raises(PermissionDenied):
            record_go_live(release, cd, GO_LIVE)

    def test_missing_date_refused(self):
        release = _closed_release()
        requester = UserFactory(role=User.Role.REQUESTER)

        with pytest.raises(ValidationError):
            record_go_live(release, requester, None)


def _go_live_url(release):
    return reverse("backlog:go_live", args=[release.pk])


class TestRecordGoLiveView:
    def test_requester_post_saves(self, client):
        release = _closed_release()
        client.force_login(UserFactory(role=User.Role.REQUESTER))

        response = client.post(_go_live_url(release), {"go_live_date": "2026-12-01"})

        assert response.status_code == 302
        release.refresh_from_db()
        assert str(release.production_go_live_date) == "2026-12-01"

    def test_cd_post_forbidden(self, client):
        release = _closed_release()
        client.force_login(UserFactory(role=User.Role.CD))

        assert client.post(_go_live_url(release), {"go_live_date": "2026-12-01"}).status_code == 403

    def test_get_never_writes(self, client):
        release = _closed_release()
        client.force_login(UserFactory(role=User.Role.REQUESTER))

        assert client.get(_go_live_url(release)).status_code == 405
        release.refresh_from_db()
        assert release.production_go_live_date is None


class TestGoLiveButtonVisibility:
    """Issue #65: the modal button is only for the not-yet-recorded state."""

    def _detail_page_for(self, client, release):
        requester = UserFactory(role=User.Role.REQUESTER)
        client.force_login(requester)
        return client.get(reverse("backlog:release_detail", args=[release.pk])).content.decode()

    def test_button_hidden_once_date_is_set(self, client):
        release = ReleaseFactory(is_open=False, production_go_live_date=GO_LIVE)

        html = self._detail_page_for(client, release)

        assert 'data-bs-target="#goLiveModal"' not in html

    def test_button_present_until_date_is_set(self, client):
        release = _closed_release()

        html = self._detail_page_for(client, release)

        assert 'data-bs-target="#goLiveModal"' in html
