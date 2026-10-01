"""Model tests for the ERD spec `.opencode/specs/database-scheme.md` section 4.5."""

import pytest

from apps.backlog.tests.factories import ECFactory, UserFactory
from apps.documents.tests.factories import DocumentVersionFactory

pytestmark = pytest.mark.django_db


class TestDocumentVersion:
    """Spec 4.5."""

    def test_document_version_creation(self):
        ec = ECFactory()
        user = UserFactory()
        document_version = DocumentVersionFactory(ec=ec, uploaded_by=user)

        assert document_version.ec == ec
        assert document_version.uploaded_by == user
        assert document_version.version_number.startswith("v")
        assert document_version.file.name.endswith(".pdf")

    def test_valid_document_passes_validation(self):
        document_version = DocumentVersionFactory()

        document_version.full_clean()
