import factory
from django.contrib.auth import get_user_model

from apps.backlog.tests.factories import UserFactory
from apps.documents.tests.factories import DocumentVersionFactory
from apps.workflow.models import Review

User = get_user_model()


class ReviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Review

    document_version = factory.SubFactory(DocumentVersionFactory)
    cd = factory.SubFactory(UserFactory, role=User.Role.CD)
    decision = Review.Decision.APPROVED
    comment = factory.Sequence(lambda n: f"Review comment {n}")
