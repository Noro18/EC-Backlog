from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django_q.tasks import async_task

from apps.backlog.models import EC  # workflow → backlog: downward, always allowed


def queue_cd_assigned(ec) -> None:
    """RF08: after the creating transaction commits, enqueue the CD email."""
    transaction.on_commit(lambda: async_task(send_cd_assigned_email, ec.pk))


def send_cd_assigned_email(ec_id: int) -> None:
    """django-q2 task: re-fetch the EC, guard, send. Never raise."""
    try: # check if in between ec ho id ne sei iha ga lae 
        
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
