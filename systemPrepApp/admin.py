from django.contrib import admin
from .models import *


class MachineChecklistStatusInline(admin.TabularInline):
    model = MachineChecklistStatus
    extra = 0
    fields = ('checklist_item', 'status', 'notes')
    raw_id_fields = ('checklist_item',)


class MachineToolStatusInline(admin.TabularInline):
    model = MachineToolStatus
    extra = 0
    fields = ('tool', 'status')
    raw_id_fields = ('tool',)


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = (
        'hostname', 'ip_address', 'department',
        'assigned_user', 'assignment_date',
        'overall_status', 'is_lead', 'last_checkin'
    )
    list_filter = (
        'department', 'overall_status',
        'is_lead', 'last_checkin'
    )
    search_fields = ('hostname', 'ip_address', 'assigned_user')
    inlines = [
        MachineChecklistStatusInline,
        MachineToolStatusInline,  
    ]
    filter_horizontal = ('optional_tools',)

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    filter_horizontal = ('productivity_tools',)

@admin.register(ProductivityTool)
class ProductivityToolAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'optional')
    list_filter = ('optional',)
    search_fields = ('name', 'description')

@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'is_critical')
    list_filter = ('is_critical',)
    search_fields = ('name', 'description')
    list_editable = ('order', 'is_critical')

@admin.register(MachineChecklistStatus)
class MachineChecklistStatusAdmin(admin.ModelAdmin):
    list_display = ('machine', 'checklist_item', 'status', 'last_updated')
    list_filter = ('status', 'checklist_item__name', 'machine__hostname')
    search_fields = ('machine__hostname', 'checklist_item__name', 'notes')
    raw_id_fields = ('machine', 'checklist_item')


@admin.register(MachineToolStatus)
class MachineToolStatusAdmin(admin.ModelAdmin):
    list_display = ('machine', 'tool', 'status', 'last_checked')
    list_filter = ('status', 'tool')
    search_fields = ('machine__hostname', 'tool__name')
    raw_id_fields = ('machine', 'tool')

@admin.register(AgentInstallationReport)
class AgentInstallationReportAdmin(admin.ModelAdmin):
    list_display = ('machine', 'status', 'reported_at')
    list_filter = ('status', 'reported_at')
    search_fields = ('machine__hostname', )
    ordering = ('-reported_at',)
