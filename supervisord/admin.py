# -*- coding: utf-8 -*-
# kate: space-indent on; indent-width 4; replace-tabs on;

from django.contrib import admin

from supervisord.models import Supervisor, Process
from supervisord.forms  import ProcessForm

admin.site.register(Supervisor)


class ProcessAdmin(admin.ModelAdmin):
    list_display = ['name', 'supervisor', 'get_process_state']
    form = ProcessForm

    def get_process_state(self, obj):
        return obj.info['statename']

    get_process_state.short_description = "State"

admin.site.register(Process, ProcessAdmin)
