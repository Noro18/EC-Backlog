from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django_q.tasks import async_task

from apps.accounts.models import User  # workflow → accounts: downward, allowed
from apps.backlog.models import EC  # workflow → backlog: downward, always allowed
from apps.workflow.models import Review
from apps.workflow.selectors import latest_version


def queue_cd_assigned(ec) -> None:
    """RF08: after the creating transaction commits, enqueue the CD email."""
    transaction.on_commit(lambda: async_task(send_cd_assigned_email, ec.pk))


def send_cd_assigned_email(ec_id: int) -> None:
    """django-q2 task: re-fetch the EC, guard, send. Never raise."""
    try:  # check if in between ec ho id ne sei iha ga lae
        ec = EC.objects.select_related("requester", "responsible_cd").get(pk=ec_id)
    except EC.DoesNotExist:
        return  # EC deleted before the worker ran — nothing to notify about
    cd = ec.responsible_cd
    if not cd.email:
        return  # nowhere to send — skip instead of crashing the worker
    link = f"{settings.SITE_URL.rstrip('/')}{reverse('backlog:ec_detail', args=[ec.pk])}"
    subject = f"EC {ec.ec_code}: validação pendente"
    body = (
        f"Olá {cd.full_name or cd.username},\n"
        f"\n"
        f"Uma nova especificação foi atribuída a você para validação.\n"
        f"\n"
        f"EC: EC-{ec.ec_code}\n"
        f"Referência: {ec.reference}\n"
        f"Descrição: {ec.description}\n"
        f"Solicitante: {ec.requester.full_name or ec.requester.username}\n"
        f"\n"
        f"Ver detalhes: {link}\n"
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [cd.email])


def queue_decision_made(ec) -> None:
    """RF10: after the decision transaction commits, enqueue the requester email."""

    transaction.on_commit(lambda: async_task(send_decision_email, ec.pk))


def send_decision_email(ec_id: int) -> None:
    """django-q2 task: re-fetch the EC + its latest review, guard, send. Never raise."""

    try:  # check if in between ec ho id ne sei iha ga lae
        ec = EC.objects.select_related("requester", "responsible_cd").get(pk=ec_id)
    except EC.DoesNotExist:
        return  # EC del

    version = latest_version(ec)
    if version is None:
        return  # versions deleted before the worker ran — nothing to report
    try:
        review = version.review
    except Review.DoesNotExist:
        return  # decision deleted before the worker ran — nothing to report
    requester = ec.requester
    if requester is None or not requester.email:
        return  # nowhere to send — skip instead of crashing the worker
    link = f"{settings.SITE_URL.rstrip('/')}{reverse('backlog:ec_detail', args=[ec.pk])}"
    cd_name = review.cd.full_name or review.cd.username
    if review.decision == Review.Decision.APPROVED:
        subject = f"EC {ec.ec_code}: aprovada"
        outcome = "aprovada pelo CD"
        reason_block = ""
    else:
        subject = f"EC {ec.ec_code}: rejeitada"
        outcome = "rejeitada pelo CD"
        reason_block = f"\nMotivo: {review.comment}\n"
    body = (
        f"Olá {requester.full_name or requester.username},\n"
        f"\n"
        f"Sua especificação foi {outcome}.\n"
        f"\n"
        f"EC: EC-{ec.ec_code}\n"
        f"Referência: {ec.reference}\n"
        f"CD: {cd_name}\n"
        f"{reason_block}"
        f"\n"
        f"Ver detalhes: {link}\n"
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [requester.email])


def queue_des_routed(ec) -> None:
    """RF11: after the routing transaction commits, enqueue the DES email."""
    transaction.on_commit(lambda: async_task(send_des_routed_email, ec.pk))


def send_des_routed_email(ec_id: int) -> None:
    """django-q2 task: re-fetch the EC, mail every DES-team user. Never raise."""
    try:
        ec = EC.objects.select_related("requester", "responsible_cd").get(pk=ec_id)
    except EC.DoesNotExist:
        return  # EC deleted before the worker ran — nothing to notify about
    recipients = list(
        User.objects.filter(role=User.Role.DES_TEAM)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not recipients:
        return  # nobody in DES to tell — skip instead of crashing the worker
    link = f"{settings.SITE_URL.rstrip('/')}{reverse('backlog:ec_detail', args=[ec.pk])}"
    cd = ec.responsible_cd
    requester = ec.requester
    subject = f"EC {ec.ec_code}: enviada ao DES"
    body = (
        f"Olá,\n"
        f"\n"
        f"Uma especificação aprovada foi enviada ao DES para implementação.\n"
        f"\n"
        f"EC: EC-{ec.ec_code}\n"
        f"Referência: {ec.reference}\n"
        f"Descrição: {ec.description}\n"
        f"CD que aprovou: {cd.full_name or cd.username if cd else '-'}\n"
        f"Enviada por: {requester.full_name or requester.username if requester else '-'}\n"
        f"\n"
        f"Ver detalhes: {link}\n"
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)
