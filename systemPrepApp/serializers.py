from rest_framework import serializers
from .models import *

# --------------------------
# Machine Serializers
# --------------------------

class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = ['hostname', 'ip_address', 'last_seen', 'overall_status']
        read_only_fields = ['last_seen', 'overall_status']

    def create(self, validated_data):
        hostname = validated_data.get('hostname')
        ip_address = validated_data.get('ip_address')
        machine, created = Machine.objects.update_or_create(
            hostname=hostname,
            defaults={'ip_address': ip_address}
        )
        return machine


class MachineDepartmentUpdateSerializer(serializers.ModelSerializer):
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
# Productivity Tool Serializers
# --------------------------

class ProductivityToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductivityTool
        fields = ['id', 'name', 'description', 'optional']


class AgentToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductivityTool
        fields = ['id', 'name', 'description', 'download_link', 'version']

# --------------------------
# Checklist Status Serializers
# --------------------------

class ChecklistStatusSerializer(serializers.Serializer):
    checklist_item_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=CHECKLIST_STATUS_CHOICES)
    notes = serializers.CharField(allow_blank=True, required=False)

    def validate_checklist_item_id(self, value):
        if not ChecklistItem.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Checklist item not found.")
        return value


class MachineChecklistStatusSerializer(serializers.ModelSerializer):
    checklist_item_id = serializers.PrimaryKeyRelatedField(
        queryset=ChecklistItem.objects.all(), source='checklist_item', write_only=True
    )
    checklist_item_name = serializers.CharField(source='checklist_item.name', read_only=True)
    checklist_item_description = serializers.CharField(source='checklist_item.description', read_only=True)
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
# Bulk Checklist Status Updater
# --------------------------

class MachineChecklistStatusBulkUpdateSerializer(serializers.Serializer):
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
# Agent API Serializers
# --------------------------

class AgentChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistItem
        fields = ['id', 'name', 'description', 'order', 'is_critical']


class AgentMachineTasksSerializer(serializers.ModelSerializer):
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
            required = obj.department.productivity_tools.filter(optional=False)
            return AgentToolSerializer(required, many=True).data
        return []

    def get_checklist_items_status(self, obj):
        all_items = ChecklistItem.objects.all().order_by('order')
        machine_statuses = {
            s.checklist_item_id: s.status for s in obj.checklist_statuses.all()
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
    
class ChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistItem
        fields = ['id', 'name', 'description', 'order', 'is_critical']