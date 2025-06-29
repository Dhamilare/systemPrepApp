from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings
from wsgiref.util import FileWrapper
from django.db.models import Count
import os
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_api_key.permissions import HasAPIKey
from django.db.models import Prefetch
from .models import *
from .serializers import *
from rest_framework.decorators import api_view
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin

# Frontend Dashboard View
class DashboardView(LoginRequiredMixin, ListView):
    model = Machine
    template_name = 'dashboard.html'
    context_object_name = 'machines'

    def get_queryset(self):
        return Machine.objects.select_related('department').order_by('hostname')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['departments'] = Department.objects.prefetch_related(
            Prefetch('productivity_tools', queryset=ProductivityTool.objects.order_by('name'))
        ).order_by('name')

        context['all_productivity_tools'] = ProductivityTool.objects.all().order_by('name')
        context['all_checklist_items'] = ChecklistItem.objects.all().order_by('name')
        context['current_time'] = timezone.now() 

        return context
    
@api_view(['POST'])
def assign_department(request, machine_id):
    machine = get_object_or_404(Machine, id=machine_id)
    new_department_id = request.data.get('department_id')

    if machine.department is not None:
        if new_department_id is None or str(machine.department.id) != str(new_department_id):
            return Response(
                {"detail": "This machine is already assigned to a department and cannot be reassigned."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
    # Resolve the new department object
    if new_department_id:
        department = get_object_or_404(Department, id=new_department_id)
    else:
        department = None

    machine.department = department
    machine.save()

    return Response(MachineSerializer(machine).data, status=status.HTTP_200_OK)


# Agent API: Register/Check-in
class AgentRegisterCheckinView(APIView):
    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request):
        serializer = MachineSerializer(data=request.data)
        if serializer.is_valid():
            machine = serializer.save()
            if machine.overall_status == 'PENDING':
                machine.overall_status = 'IN_PROGRESS'
                machine.save()

            return Response({
                "message": "Machine registered/checked in successfully.",
                "hostname": machine.hostname,
                "overall_status": machine.overall_status,
                "id": machine.id
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Assign Department to Machine
class MachineAssignDepartmentView(APIView):
    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request, pk):
        machine = get_object_or_404(Machine, pk=pk)
        serializer = MachineDepartmentUpdateSerializer(machine, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Department assigned successfully.",
                "hostname": machine.hostname,
                "department": machine.department.name if machine.department else "Unassigned"
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# List Optional Tools (For UI Dropdown)
class OptionalProductivityToolListView(generics.ListAPIView):
    queryset = ProductivityTool.objects.filter(optional=True).order_by('name')
    serializer_class = ProductivityToolSerializer
    permission_classes = [HasAPIKey | IsAuthenticated]


# Assign Optional Tools to a Machine
class MachineOptionalToolsView(APIView):
    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request, pk):
        machine = get_object_or_404(Machine, pk=pk)
        serializer = MachineOptionalToolsSerializer(machine, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": f"Optional tools for {machine.hostname} updated successfully.",
                "hostname": machine.hostname,
                "optional_tools": serializer.data.get('optional_tools_display', [])
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# List All Checklist Items (for UI)
class AllChecklistItemsListView(generics.ListAPIView):
    queryset = ChecklistItem.objects.all().order_by('order', 'name')
    serializer_class = ChecklistItemSerializer
    permission_classes = [HasAPIKey | IsAuthenticated]


# Bulk Checklist Status Update (Admin or Agent)
class MachineChecklistStatusView(APIView):
    """
    API endpoint to bulk update checklist statuses for a specific machine.
    """
    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        # Get machine instance by primary key (ID)
        machine = get_object_or_404(Machine, pk=pk)

        # Initialize the bulk serializer with machine context
        serializer = MachineChecklistStatusBulkUpdateSerializer(
            data=request.data,
            context={'machine': machine}
        )

        # Validate and save the bulk checklist status updates
        if serializer.is_valid():
            updated_statuses = serializer.save()  # Calls `create()` method in the serializer
            return Response({
                "message": "Checklist statuses updated successfully.",
                "updated_checklist_items": MachineChecklistStatusSerializer(updated_statuses, many=True).data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Agent Tasks Fetch (Tools + Checklist)
class AgentMachineTasksView(generics.RetrieveAPIView):
    serializer_class = AgentMachineTasksSerializer
    permission_classes = [HasAPIKey]

    def get_object(self):
        hostname = self.request.META.get('HTTP_X_HOSTNAME')
        if hostname:
            return get_object_or_404(Machine, hostname=hostname)
        return get_object_or_404(Machine, pk=self.kwargs['pk'])  # fallback for testing


#Download Agent EXE
@login_required
def download_agent_exe(request):
    exe_path = os.path.join(settings.BASE_DIR, 'systemPrepApp', 'dist', 'client_agent.exe')
    if os.path.exists(exe_path):
        wrapper = FileWrapper(open(exe_path, 'rb'))
        response = HttpResponse(wrapper, content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="client_agent.exe"'
        return response

    return HttpResponse("Agent executable not found.", status=404)


class DepartmentsListView(LoginRequiredMixin, ListView):
    model = Department
    template_name = 'departments_list.html' 
    context_object_name = 'departments'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()

        queryset = queryset.annotate(
            machines_count=Count('machines', distinct=True)
        )

        queryset = queryset.prefetch_related('productivity_tools')

        return queryset


class ChecklistItemsListView(LoginRequiredMixin, ListView):
    model = ChecklistItem
    template_name = 'checklist_items_list.html'
    context_object_name = 'checklist_items'
    paginate_by = 10 

    def get_queryset(self):
        return super().get_queryset()
    

class MachineDetailView(LoginRequiredMixin, DetailView):
    model = Machine 
    template_name = 'machine_detail.html' 
    context_object_name = 'machine'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

# Agent reports installation completion
class AgentInstallationCompletedView(APIView):
    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request):
        hostname = request.data.get("hostname")
        ip_address = request.data.get("ip_address")
        installed = request.data.get("installed", [])
        status_text = request.data.get("status", "completed")

        if not hostname:
            return Response({"detail": "Missing hostname"}, status=400)

        try:
            machine = Machine.objects.get(hostname=hostname)
        except Machine.DoesNotExist:
            return Response({"detail": "Machine not found"}, status=404)

        AgentInstallationReport.objects.create(
            machine=machine,
            status=status_text,
            installed_tools=installed
        )

        machine.overall_status = 'READY'
        machine.save(update_fields=["overall_status"])

        return Response({
            "message": "Installation completion report recorded.",
            "machine": machine.hostname,
            "status": machine.overall_status
        }, status=201)
