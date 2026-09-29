import factory

from apps.backlog.tests.factories import ECFactory, UserFactory
from apps.documents.models import DocumentVersion


class DocumentVersionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DocumentVersion

    ec = factory.SubFactory(ECFactory)
    version_number = factory.Sequence(lambda n: f"v{n}")
    file = factory.django.FileField(data=b"Dummy file content", filename="spec.pdf")
    uploaded_by = factory.SubFactory(UserFactory)
