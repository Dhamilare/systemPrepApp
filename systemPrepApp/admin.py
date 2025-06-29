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
        'hostname',
        'ip_address',
        'department',
        'overall_status',
        'is_lead',
        'last_checkin'
    )
    list_filter = (
        'department',
        'overall_status',
        'is_lead',
        'last_checkin'
    )
    search_fields = ('hostname', 'ip_address')
    # Add inlines to manage related objects directly from the Machine detail page
    inlines = [
        MachineChecklistStatusInline,
        # MachineToolStatusInline, # Uncomment this if you are using MachineToolStatus for granular tool tracking
    ]
    filter_horizontal = ('optional_tools',) # Use this for ManyToMany fields directly on Machine


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    filter_horizontal = ('productivity_tools',) # Allow selecting multiple tools easily

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
    list_editable = ('order', 'is_critical') # Allow quick editing of order and critical status

@admin.register(MachineChecklistStatus)
class MachineChecklistStatusAdmin(admin.ModelAdmin):
    list_display = ('machine', 'checklist_item', 'status', 'last_updated')
    list_filter = ('status', 'checklist_item__name', 'machine__hostname') # Filter by machine and checklist item name
    search_fields = ('machine__hostname', 'checklist_item__name', 'notes')
    raw_id_fields = ('machine', 'checklist_item') # For better performance if you have many instances


@admin.register(AgentInstallationReport)
class AgentInstallationReportAdmin(admin.ModelAdmin):
    list_display = ('machine', 'status', 'reported_at')
    list_filter = ('status', 'reported_at')
    search_fields = ('machine__hostname', )
    ordering = ('-reported_at', )