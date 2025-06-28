from rest_framework import serializers
from .models import *

# --------------------------
# 1. Core Serializers (Dependencies first)
# These must be defined before any other serializers that use them.
# --------------------------

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'description']

class ProductivityToolSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = ProductivityTool 
        fields = ['id', 'name', 'description', 'optional']

class AgentToolSerializer(serializers.ModelSerializer):
    """
    Serializer for Tool model specifically for the Agent API.
    Assumes 'download_link' and 'version' fields exist on the Tool model.
    If not, you will need to add them to core/models.py or remove from here.
    """
    class Meta:
        model = ProductivityTool
        fields = ['id', 'name', 'description', 'download_link', 'version']

class ChecklistItemSerializer(serializers.ModelSerializer):
    """
    Serializer for the ChecklistItem model.
    """
    class Meta:
        model = ChecklistItem
        fields = ['id', 'name', 'description', 'order', 'is_critical']


# --------------------------
# 2. Machine Serializers
# These can now correctly reference DepartmentSerializer and ToolSerializer.
# --------------------------

class MachineSerializer(serializers.ModelSerializer):
    """
    Main serializer for the Machine model, including nested department and optional tools.
    """
    department = DepartmentSerializer(read_only=True) # Nested serializer for department info
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source='department', write_only=True, required=False, allow_null=True
    )
    optional_tools = ProductivityToolSerializer(many=True, read_only=True) 
    overall_status_display = serializers.CharField(source='get_overall_status_display', read_only=True)

    class Meta:
        model = Machine
        fields = [
            'id', 'hostname', 'ip_address', 'api_key', 'last_check_in',
            'department', 'department_id', 'optional_tools', 'overall_status',
            'overall_status_display', 'is_lead', 'assigned_user', 'assignment_date'
        ]
        read_only_fields = ['id', 'api_key', 'last_check_in', 'overall_status', 'overall_status_display']


class MachineDepartmentUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating only the department of a Machine.
    """
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source='department', write_only=True
    )

    class Meta:
        model = Machine
        fields = ['id', 'hostname', 'department_id']
        read_only_fields = ['id', 'hostname']

    def update(self, instance, validated_data):
        instance.department = validated_data.get('department', instance.department)
        instance.save()
        return instance


class MachineOptionalToolsSerializer(serializers.ModelSerializer):
    """
    Serializer for updating optional tools assigned to a Machine.
    """
    optional_tool_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=ProductivityTool.objects.filter(optional=True),
        source='optional_tools',
        write_only=True
    )
    optional_tools_display = serializers.StringRelatedField(
        many=True, source='optional_tools', read_only=True
    )

    class Meta:
        model = Machine
        fields = ['id', 'hostname', 'optional_tool_ids', 'optional_tools_display']
        read_only_fields = ['id', 'hostname', 'optional_tools_display']

    def update(self, instance, validated_data):
        if 'optional_tools' in validated_data:
            instance.optional_tools.set(validated_data['optional_tools'])
        instance.save()
        return instance


# --------------------------
# 3. Checklist Status Serializers
# --------------------------

class ChecklistStatusSerializer(serializers.Serializer):
    """
    Basic serializer for a single checklist item status, used in bulk updates.
    """
    checklist_item_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=CHECKLIST_STATUS_CHOICES)
    notes = serializers.CharField(allow_blank=True, required=False)

    def validate_checklist_item_id(self, value):
        if not ChecklistItem.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Checklist item not found.")
        return value


class MachineChecklistStatusSerializer(serializers.ModelSerializer):
    """
    Serializer for MachineChecklistStatus, includes detailed checklist item info.
    """
    checklist_item_id = serializers.PrimaryKeyRelatedField(
        queryset=ChecklistItem.objects.all(), source='checklist_item', write_only=True
    )
    checklist_item_name = serializers.CharField(source='checklist_item.name', read_only=True)
    checklist_item_description = serializers.CharField(source='checklist_item.description', read_only=True)
    # Assuming 'order' field exists on ChecklistItem model. If not, remove this line or add the field.
    checklist_item_order = serializers.IntegerField(source='checklist_item.order', read_only=True)

    class Meta:
        model = MachineChecklistStatus
        fields = [
            'id', 'machine', 'checklist_item_id', 'checklist_item_name',
            'checklist_item_description', 'checklist_item_order',
            'status', 'notes', 'last_updated'
        ]
        read_only_fields = ['id', 'machine', 'last_updated']

    def update(self, instance, validated_data):
        instance.status = validated_data.get('status', instance.status)
        instance.notes = validated_data.get('notes', instance.notes)
        instance.save()
        return instance

# --------------------------
# 4. Bulk Checklist Status Updater
# --------------------------

class MachineChecklistStatusBulkUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk updating multiple MachineChecklistStatus records.
    """
    checklist_statuses = ChecklistStatusSerializer(many=True)

    def create(self, validated_data):
        machine = self.context.get('machine')
        if not machine:
            raise serializers.ValidationError("Machine context is required.")

        updated_statuses = []
        for status_data in validated_data['checklist_statuses']:
            checklist_item = ChecklistItem.objects.get(pk=status_data['checklist_item_id'])
            obj, _ = MachineChecklistStatus.objects.update_or_create(
                machine=machine,
                checklist_item=checklist_item,
                defaults={
                    'status': status_data['status'],
                    'notes': status_data.get('notes', '')
                }
            )
            updated_statuses.append(obj)
        return updated_statuses


# --------------------------
# 5. Agent API Serializers
# --------------------------

class AgentMachineTasksSerializer(serializers.ModelSerializer):
    """
    Serializer to provide machine-specific tasks and checklist status to the agent.
    """
    required_tools = serializers.SerializerMethodField()
    optional_tools_assigned = AgentToolSerializer(source='optional_tools', many=True, read_only=True)
    checklist_items_status = serializers.SerializerMethodField()

    class Meta:
        model = Machine
        fields = [
            'id', 'hostname', 'overall_status',
            'required_tools', 'optional_tools_assigned', 'checklist_items_status'
        ]

    def get_required_tools(self, obj):
        if obj.department:
            # Assuming 'productivity_tools' is the ManyToManyField name on the Department model
            # and 'optional=False' indicates required tools.
            required = obj.department.productivity_tools.filter(optional=False)
            return AgentToolSerializer(required, many=True).data
        return []

    def get_checklist_items_status(self, obj):
        # Assuming 'order' field exists on ChecklistItem model
        all_items = ChecklistItem.objects.all().order_by('order')
        # Use the default reverse accessor 'machinecheckliststatus_set'
        machine_statuses = {
            s.checklist_item_id: s.status for s in obj.machinecheckliststatus_set.all()
        }

        return [
            {
                'id': item.id,
                'name': item.name,
                'description': item.description,
                'order': item.order,
                'is_critical': item.is_critical,
                'current_status': machine_statuses.get(item.id, 'PENDING')
            }
            for item in all_items
        ]