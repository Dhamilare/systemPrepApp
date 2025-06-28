from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings
from wsgiref.util import FileWrapper
from django.views import View
import os
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_api_key.permissions import HasAPIKey
from django.db.models import Prefetch
from .models import *
from .serializers import *
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator


# Frontend Dashboard View
@method_decorator(login_required, name='dispatch')
class DashboardView(View):
    def get(self, request):
        machines = Machine.objects.select_related('department').order_by('hostname')
        departments = Department.objects.prefetch_related(
            Prefetch('productivity_tools', queryset=ProductivityTool.objects.order_by('name'))
        ).order_by('name')

        context = {
            'machines': machines,
            'departments': departments,
            'current_time': timezone.now()
        }
        return render(request, 'dashboard.html', context)


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
def download_agent_exe(request):
    exe_path = os.path.join(settings.BASE_DIR, 'systemPrepApp', 'dist', 'client_agent.exe')
    if os.path.exists(exe_path):
        wrapper = FileWrapper(open(exe_path, 'rb'))
        response = HttpResponse(wrapper, content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="client_agent.exe"'
        return response

    return HttpResponse("Agent executable not found.", status=404)
