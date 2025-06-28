from django.urls import path
from django.contrib import admin
from .views import *
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('', DashboardView.as_view(), name='dashboard'),
    path('machine/<int:pk>/assign_department/', MachineAssignDepartmentView.as_view(), name='machine_assign_department'),
    path('machine/<int:pk>/optional_tools/', MachineOptionalToolsView.as_view(), name='machine_optional_tools'),
    path('tools/optional_list/', OptionalProductivityToolListView.as_view(), name='optional_tools_list'),
    path('checklist/items/', AllChecklistItemsListView.as_view(), name='all_checklist_items'),
    path('machine/<int:pk>/checklist_status/', MachineChecklistStatusView.as_view(), name='machine_checklist_status'),
    path('agent/tasks/<int:pk>/', AgentMachineTasksView.as_view(), name='agent_get_tasks'),
    path('download/agent/', download_agent_exe, name='download_agent_exe'),
    path('agent/checkin/', AgentRegisterCheckinView.as_view(), name='agent_checkin'),
    path('departments/', DepartmentsListView.as_view(), name='departments_list'),
    path('checklist-items/', ChecklistItemsListView.as_view(), name='checklist_items_list'),
    path('machine/<int:pk>/', MachineDetailView.as_view(), name='machine_detail'),
]