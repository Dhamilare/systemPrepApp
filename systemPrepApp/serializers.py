from rest_framework import serializers
from .models import *

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
    
class ProductivityToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductivityTool
        fields = ['id', 'name', 'description', 'optional']


class MachineOptionalToolsSerializer(serializers.ModelSerializer):
    # This field will receive a list of ProductivityTool IDs from the frontend
    optional_tool_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=ProductivityTool.objects.filter(optional=True), # Only allow optional tools to be assigned here
        source='optional_tools', # Map to the 'optional_tools' ManyToMany field on the Machine model
        write_only=True # This field is only for writing (sending IDs)
    )
    # For reading/displaying, we can also expose the names of selected tools
    optional_tools_display = serializers.StringRelatedField(many=True, source='optional_tools', read_only=True)

    class Meta:
        model = Machine
        fields = ['id', 'hostname', 'optional_tool_ids', 'optional_tools_display']
        read_only_fields = ['id', 'hostname', 'optional_tools_display'] # 'id' and 'hostname' are read-only for this update

    def update(self, instance, validated_data):
        # Update the ManyToMany field 'optional_tools'
        # .set() is used for ManyToMany relationships to replace the current set of related objects
        if 'optional_tools' in validated_data:
            instance.optional_tools.set(validated_data['optional_tools'])
        instance.save() # Save the instance to persist changes to other fields if any, though ManyToMany often saves independently
        return instance
    
class ChecklistItemSerializer(serializers.ModelSerializer):
    """
    Serializer for listing ChecklistItem objects.
    """
    class Meta:
        model = ChecklistItem
        fields = ['id', 'name', 'description', 'order', 'is_critical']
        read_only_fields = ['id', 'name', 'description', 'order', 'is_critical'] # Read-only for dashboard display

class MachineChecklistStatusSerializer(serializers.ModelSerializer):
    """
    Serializer for MachineChecklistStatus, used for reading and updating
    the status of a specific checklist item for a specific machine.
    """
    checklist_item_id = serializers.PrimaryKeyRelatedField(
        queryset=ChecklistItem.objects.all(),
        source='checklist_item',
        write_only=True # Only send ID when updating
    )
    # To display the checklist item's name and description when reading
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
        read_only_fields = ['id', 'machine', 'last_updated'] # Machine ID is usually implicit in URL for updates

    def create(self, validated_data):
        # Handle creation: ensure machine and checklist_item are unique together
        # This is typically handled by a view that processes multiple statuses at once
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance.status = validated_data.get('status', instance.status)
        instance.notes = validated_data.get('notes', instance.notes)
        instance.save()
        return instance

# Serializer to handle a list of checklist status updates for a single machine
class BulkMachineChecklistStatusSerializer(serializers.Serializer):
    """
    Serializer to receive a list of checklist item statuses for bulk update on a machine.
    """
    checklist_statuses = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField() # Or more specific validation if needed
        ),
        write_only=True
    )

    def to_internal_value(self, data):
        # Custom validation to ensure each item has 'checklist_item_id' and 'status'
        for item in data.get('checklist_statuses', []):
            if 'checklist_item_id' not in item or 'status' not in item:
                raise serializers.ValidationError("Each checklist status must have 'checklist_item_id' and 'status'.")
            if 'notes' not in item:
                item['notes'] = '' # Ensure notes field is present, even if empty
        return super().to_internal_value(data)

    def update(self, machine_instance, validated_data):
        """
        Updates or creates MachineChecklistStatus entries for a given machine.
        `machine_instance` is the Machine object to update.
        `validated_data` contains `checklist_statuses` which is a list of dicts.
        """
        updates = validated_data.get('checklist_statuses', [])
        updated_statuses = []

        for item_data in updates:
            checklist_item_id = item_data.get('checklist_item_id')
            new_status = item_data.get('status')
            notes = item_data.get('notes', '')

            if not checklist_item_id or not new_status:
                continue # Skip invalid entries

            checklist_item = ChecklistItem.objects.filter(id=checklist_item_id).first()
            if not checklist_item:
                continue # Skip if checklist item doesn't exist

            # Get or create the MachineChecklistStatus instance
            status_instance, created = MachineChecklistStatus.objects.get_or_create(
                machine=machine_instance,
                checklist_item=checklist_item,
                defaults={'status': new_status, 'notes': notes}
            )
            if not created:
                # Update existing instance
                status_instance.status = new_status
                status_instance.notes = notes
                status_instance.save()
            updated_statuses.append(status_instance)

        # Return serialized representation of the updated statuses for feedback
        return [MachineChecklistStatusSerializer(s).data for s in updated_statuses]
    

class AgentToolSerializer(serializers.ModelSerializer):
    """
    Serializer for ProductivityTool when queried by an agent.
    Includes download link for automation.
    """
    class Meta:
        model = ProductivityTool
        fields = ['id', 'name', 'description', 'download_link', 'version']

class AgentChecklistItemSerializer(serializers.ModelSerializer):
    """
    Serializer for ChecklistItem when queried by an agent.
    """
    class Meta:
        model = ChecklistItem
        fields = ['id', 'name', 'description', 'order', 'is_critical']

class AgentMachineTasksSerializer(serializers.ModelSerializer):
    """
    Serializer to represent all tasks (required tools, optional tools, checklist items)
    assigned to a specific machine, for agent consumption.
    """
    # Tools required by the machine's department
    required_tools = serializers.SerializerMethodField()
    # Optional tools explicitly assigned to this machine
    optional_tools_assigned = AgentToolSerializer(source='optional_tools', many=True, read_only=True)
    # Checklist items and their current status for this machine
    checklist_items_status = serializers.SerializerMethodField()

    class Meta:
        model = Machine
        fields = [
            'id', 'hostname', 'overall_status',
            'required_tools', 'optional_tools_assigned', 'checklist_items_status'
        ]

    def get_required_tools(self, obj):
        # This method fetches tools based on the machine's assigned department
        if obj.department:
            # Filter out optional tools if the department includes them,
            # assuming 'required' means not optional from the department's perspective for an agent.
            # Adjust this logic based on how you define 'required' vs 'optional' for agents.
            required_tools_from_dept = obj.department.productivity_tools.filter(optional=False)
            return AgentToolSerializer(required_tools_from_dept, many=True).data
        return []

    def get_checklist_items_status(self, obj):
        # Get all defined checklist items and merge with the machine's current status
        all_items = ChecklistItem.objects.all().order_by('order')
        machine_statuses = {mcs.checklist_item_id: mcs.status for mcs in obj.checklist_statuses.all()}

        result = []
        for item in all_items:
            result.append({
                'id': item.id,
                'name': item.name,
                'description': item.description,
                'order': item.order,
                'is_critical': item.is_critical,
                'current_status': machine_statuses.get(item.id, 'PENDING') # Default to PENDING if no status exists
            })
        return result
