# -*- coding: utf-8 -*-
# kate: space-indent on; indent-width 4; replace-tabs on;

from django.contrib import admin

from kvm.models import *

def brstart(modeladmin, request, queryset):
    for br in queryset:
        br.start()

brstart.short_description = "Start Bridge"

def brstop(modeladmin, request, queryset):
    for br in queryset:
        br.stop()

brstop.short_description = "Stop Bridge"


class BridgeAdmin(admin.ModelAdmin):
    list_display = ["commonname", "name", "ip4address", "dnsmasq", "get_br_state"]
    actions      = [brstart, brstop]

    def get_br_state(self, obj):
        return obj.process.info['statename']

    get_br_state.short_description = "Bridge State"


class SnapshotInline(admin.StackedInline):
    model = Snapshot


def vmstart(modeladmin, request, queryset):
    for vm in queryset:
        vm.start()

vmstart.short_description = "Start VM"

def vmstop(modeladmin, request, queryset):
    for vm in queryset:
        vm.stop()

vmstop.short_description = "Stop (kill) VM"

def vmshutdown(modeladmin, request, queryset):
    for vm in queryset:
        vm.shutdown()

vmshutdown.short_description = "Stop VM gracefully by shutting down the OS"

def vmcommit(modeladmin, request, queryset):
    for vm in queryset:
        vm.commit()

vmcommit.short_description = "Commit changes to the disk file (snapshot mode only)"


class VirtualMachineAdmin(admin.ModelAdmin):
    list_display = ["name", "macaddress", "ip4address", "vncport", "runsnapshot", "get_vm_state"]
    actions      = [vmstart, vmstop, vmshutdown, vmcommit]
    inlines      = [SnapshotInline]

    def get_vm_state(self, obj):
        return obj.process.info['statename']

    get_vm_state.short_description = "VM State"



admin.site.register(Bridge, BridgeAdmin)
admin.site.register(VirtualMachine, VirtualMachineAdmin)
