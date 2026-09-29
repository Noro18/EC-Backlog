import factory
from django.contrib.auth import get_user_model

from apps.backlog.models import EC, Release

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    first_name = factory.LazyAttribute(lambda o: o.username)
    role = User.Role.REQUESTER


class ReleaseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Release

    year = 2026
    number_sequence = factory.Sequence(lambda n: n + 1)
    release_code = factory.LazyAttribute(lambda o: f"TT_ON_{o.year}-{o.number_sequence:03d}")
    capacity = 10


class ECFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EC

    year = 2026
    number_sequence = factory.Sequence(lambda n: n + 1)
    reference = factory.LazyAttribute(lambda o: f"CR{o.year}{o.number_sequence:03d}")
    description = factory.Sequence(lambda n: f"Change request {n + 1}")
    release = factory.SubFactory(ReleaseFactory)
    requester = factory.SubFactory(UserFactory)
