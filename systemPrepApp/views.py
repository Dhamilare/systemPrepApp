from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views import View
from rest_framework import generics

from rest_framework.permissions import IsAuthenticated
from rest_framework_api_key.permissions import HasAPIKey

from .models import *
from .serializers import *

import os
from django.conf import settings
from django.http import HttpResponse
from wsgiref.util import FileWrapper


class DashboardView(View):
    def get(self, request, *args, **kwargs):
        machines = Machine.objects.all().select_related('department').order_by('hostname')
        departments = Department.objects.prefetch_related(
            Prefetch('productivity_tools', queryset=ProductivityTool.objects.all().order_by('name'))
        ).order_by('name')

        context = {
            'machines': machines,
            'departments': departments,
            'current_time': timezone.now()
        }
        return render(request, 'dashboard.html', context)


class AgentRegisterCheckinView(APIView):
    """
    Agents can register/check-in via API key OR logged-in admin via session
    """
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
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MachineAssignDepartmentView(APIView):
    """
    Allows assignment via API key (agent) OR admin login
    """
    permission_classes = [HasAPIKey | IsAuthenticated] 

    def post(self, request, pk, *args, **kwargs):
        machine = get_object_or_404(Machine, pk=pk)
        serializer = MachineDepartmentUpdateSerializer(machine, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Department assigned successfully.",
                "hostname": machine.hostname,
                "department": machine.department.name if machine.department else "Unassigned"
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class OptionalProductivityToolListView(generics.ListAPIView):

    queryset = ProductivityTool.objects.filter(optional=True).order_by('name')
    serializer_class = ProductivityToolSerializer
    permission_classes = [HasAPIKey | IsAuthenticated]


class MachineOptionalToolsView(APIView):
    """
    API endpoint for administrators to assign optional productivity tools to a specific machine.
    Requires authentication (admin login).
    """
    permission_classes = [HasAPIKey | IsAuthenticated] 

    def post(self, request, pk, *args, **kwargs):
        machine = get_object_or_404(Machine, pk=pk)
        serializer = MachineOptionalToolsSerializer(machine, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": f"Optional tools for {machine.hostname} updated successfully.",
                "hostname": machine.hostname,
                "optional_tools": serializer.data.get('optional_tools_display', [])
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AllChecklistItemsListView(generics.ListAPIView):
    """
    API endpoint to list all defined ChecklistItem objects.
    Used by the dashboard to populate the checklist section in the machine details modal.
    """
    queryset = ChecklistItem.objects.all().order_by('order', 'name') # Order consistently
    serializer_class = ChecklistItemSerializer
    permission_classes = [HasAPIKey | IsAuthenticated]

class MachineChecklistStatusView(APIView):
    """
    API endpoint to retrieve and update checklist item statuses for a specific machine.
    """
    permission_classes = [HasAPIKey | IsAuthenticated] 

    def get(self, request, pk, *args, **kwargs):
        """
        Retrieves all checklist statuses for a given machine.
        """
        machine = get_object_or_404(Machine, pk=pk)
        # Prefetch the checklist_item to reduce queries
        machine_checklist_statuses = MachineChecklistStatus.objects.filter(machine=machine).select_related('checklist_item')
        serializer = MachineChecklistStatusSerializer(machine_checklist_statuses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk, *args, **kwargs):
    
        machine = get_object_or_404(Machine, pk=pk)
        
        # Use the BulkMachineChecklistStatusSerializer to handle the list of updates
        serializer = BulkMachineChecklistStatusSerializer(data=request.data)

        if serializer.is_valid():
            updated_data = serializer.update(machine, serializer.validated_data)
            return Response({
                "message": f"Checklist statuses for {machine.hostname} updated successfully.",
                "updated_statuses": updated_data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class AgentMachineTasksView(generics.RetrieveAPIView):
    """
    API endpoint for a machine agent to retrieve its assigned tasks:
    required tools, optional tools, and checklist items.
    The agent authenticates using its API Key (hostname).
    """
    queryset = Machine.objects.all()
    serializer_class = AgentMachineTasksSerializer
    permission_classes = [HasAPIKey] # Secure this with API Key

    def get_object(self):
        hostname = self.request.META.get('HTTP_X_HOSTNAME') # Custom header for hostname, or similar
        if hostname:
            return get_object_or_404(Machine, hostname=hostname)
        # Fallback to PK for testing, but ideally remove this for agent endpoints
        return get_object_or_404(Machine, pk=self.kwargs['pk'])
    
def download_agent_exe(request):
    exe_path = os.path.join(
        settings.BASE_DIR,           
        'systemPrepApp', 'dist',     
        'client_agent.exe'         
    )

    if os.path.exists(exe_path):
        wrapper = FileWrapper(open(exe_path, 'rb'))
        response = HttpResponse(wrapper, content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="client_agent.exe"'
        return response
    return HttpResponse("Agent executable not found.", status=404)