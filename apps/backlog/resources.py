from import_export import resources

from apps.backlog.models import EC


class ECResource(resources.ModelResource):
    class Meta:
        model = EC
        fields = ("year", "number_sequence", "reference", "description", "status")
        import_id_fields = ("year", "number_sequence")
        skip_unchanged = True
        report_skipped = True

    def before_save_instance(self, instance, row, **kwargs):
        instance.is_imported = True
        instance.requester = None
        instance.responsible_cd = None
        instance.creation_date = None
