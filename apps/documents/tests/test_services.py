import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.backlog.tests.factories import ECFactory, UserFactory
from apps.documents.services import create_first_version, create_next_version

pytestmark = pytest.mark.django_db


class TestCreateNextVersion:
    def test_minor_bump(self):
        ec = ECFactory()
        user = UserFactory()
        first = create_first_version(
            ec=ec,
            file=SimpleUploadedFile("spec.pdf", b"first content"),
            uploaded_by=user,
            change_reason="initial",
        )
        assert first.version_number == "v1.0"

        second = create_next_version(
            ec=ec,
            file=SimpleUploadedFile("spec.pdf", b"fixed content"),
            uploaded_by=user,
            change_reason="added the missing diagram",
        )

        assert second.version_number == "v1.1"
        assert ec.versions.count() == 2

    def test_major_bump(self):
        ec = ECFactory()
        user = UserFactory()
        create_first_version(
            ec=ec,
            file=SimpleUploadedFile("spec.pdf", b"first content"),
            uploaded_by=user,
            change_reason="initial",
        )
        second = create_next_version(
            ec=ec,
            file=SimpleUploadedFile("spec.pdf", b"fixed content"),
            uploaded_by=user,
            change_reason="added the missing diagram",
            major=True,
        )

        assert second.version_number == "v2.0"
        assert ec.versions.count() == 2

    def test_blank_reason_refused(self):
        ec = ECFactory()
        user = UserFactory()
        create_first_version(
            ec=ec,
            file=SimpleUploadedFile("spec.pdf", b"first content"),
            uploaded_by=user,
            change_reason="initial",
        )

        with pytest.raises(ValidationError):
            create_next_version(
                ec=ec,
                file=SimpleUploadedFile("spec.pdf", b"fixed content"),
                uploaded_by=user,
                change_reason="   ",
            )

        assert ec.versions.count() == 1
