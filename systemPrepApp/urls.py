from django.urls import path
from .views import *

urlpatterns = [
    path('agent/checkin/', AgentRegisterCheckinView.as_view(), name='agent_checkin'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('machine/<int:pk>/assign_department/', MachineAssignDepartmentView.as_view(), name='machine_assign_department'),
    path('machine/<int:pk>/optional_tools/', MachineOptionalToolsView.as_view(), name='machine_optional_tools'),
    path('tools/optional_list/', OptionalProductivityToolListView.as_view(), name='optional_tools_list'),
    path('checklist/items/', AllChecklistItemsListView.as_view(), name='all_checklist_items'),
    path('machine/<int:pk>/checklist_status/', MachineChecklistStatusView.as_view(), name='machine_checklist_status'),
    path('agent/tasks/<int:pk>/', AgentMachineTasksView.as_view(), name='agent_get_tasks'),
    path('download/agent/', download_agent_exe, name='download_agent_exe'),
]