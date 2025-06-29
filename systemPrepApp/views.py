from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings
from wsgiref.util import FileWrapper
from django.db.models import Count, Prefetch
import os

from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_api_key.permissions import HasAPIKey
from rest_framework.decorators import api_view

from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import *
from .serializers import *


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

    department = get_object_or_404(Department, id=new_department_id) if new_department_id else None
    machine.department = department
    machine.save()
    return Response(MachineSerializer(machine).data, status=status.HTTP_200_OK)


class AgentRegisterCheckinView(APIView):
    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request, *args, **kwargs):
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


class OptionalProductivityToolListView(generics.ListAPIView):
    queryset = ProductivityTool.objects.filter(optional=True).order_by('name')
    serializer_class = ProductivityToolSerializer
    permission_classes = [HasAPIKey | IsAuthenticated]


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


class AllChecklistItemsListView(generics.ListAPIView):
    queryset = ChecklistItem.objects.all().order_by('order', 'name')
    serializer_class = ChecklistItemSerializer
    permission_classes = [HasAPIKey | IsAuthenticated]


class MachineChecklistStatusView(APIView):
    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        machine = get_object_or_404(Machine, pk=pk)
        serializer = MachineChecklistStatusBulkUpdateSerializer(
            data=request.data,
            context={'machine': machine}
        )

        if serializer.is_valid():
            updated_statuses = serializer.save()
            return Response({
                "message": "Checklist statuses updated successfully.",
                "updated_checklist_items": MachineChecklistStatusSerializer(updated_statuses, many=True).data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AgentMachineTasksView(generics.RetrieveAPIView):
    serializer_class = AgentMachineTasksSerializer
    permission_classes = [HasAPIKey]

    def get_object(self):
        hostname = self.request.META.get('HTTP_X_HOSTNAME')
        if hostname:
            return get_object_or_404(Machine, hostname=hostname)
        return get_object_or_404(Machine, pk=self.kwargs['pk'])


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
        return super().get_queryset().annotate(
            machines_count=Count('machines', distinct=True)
        ).prefetch_related('productivity_tools')


class ChecklistItemsListView(LoginRequiredMixin, ListView):
    model = ChecklistItem
    template_name = 'checklist_items_list.html'
    context_object_name = 'checklist_items'
    paginate_by = 10


class MachineDetailView(LoginRequiredMixin, DetailView):
    model = Machine
    template_name = 'machine_detail.html'
    context_object_name = 'machine'


class AgentInstallationCompletedView(APIView):
    permission_classes = [HasAPIKey]

    def post(self, request, *args, **kwargs):
        serializer = InstallationReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data
        machine_id = data["machine_id"]
        status_value = data.get("status", "completed")
        installed_tools = data["installed_tools"]

        try:
            machine = Machine.objects.get(id=machine_id)
        except Machine.DoesNotExist:
            return Response({"detail": "Machine not found."}, status=404)

        AgentInstallationReport.objects.create(
            machine=machine,
            status=status_value,
            installed_tools=installed_tools
        )

        return Response({"message": "Installation report received."}, status=200)


class AgentInstallationReportView(APIView):
    permission_classes = [HasAPIKey]

    def post(self, request, *args, **kwargs):
        hostname = request.data.get("hostname")
        status_value = request.data.get("status", "completed")
        installed_tools = request.data.get("installed_tools", [])

        if not hostname:
            return Response({"error": "Hostname is required."}, status=400)

        try:
            machine = Machine.objects.get(hostname=hostname)
        except Machine.DoesNotExist:
            return Response({"error": "Machine not found."}, status=404)

        AgentInstallationReport.objects.create(
            machine=machine,
            status=status_value,
            installed_tools=installed_tools,
        )

        return Response({"message": "Installation report received."}, status=status.HTTP_200_OK)


class AgentMachineLookupView(APIView):
    permission_classes = [HasAPIKey]

    def get(self, request, *args, **kwargs):
        hostname = request.query_params.get('hostname')
        if not hostname:
            return Response({"error": "Hostname is required."}, status=400)

        try:
            machine = Machine.objects.get(hostname=hostname)
            return Response({
                "id": machine.id,
                "hostname": machine.hostname,
                "overall_status": machine.overall_status,
                "department": machine.department.name if machine.department else None
            })
        except Machine.DoesNotExist:
            return Response({"error": "Machine not found."}, status=404)