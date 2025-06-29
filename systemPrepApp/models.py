# core/models.py

from django.db import models
from django.utils import timezone # Make sure timezone is imported for DateTimeField defaults if needed

# --- Global Choices Definitions ---

# Choices for Machine's overall status
STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('IN_PROGRESS', 'In Progress'),
    ('READY', 'Ready for Deployment'),
    ('ERROR', 'Error'),
]

# Choices for individual Checklist Item status
CHECKLIST_STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('IN_PROGRESS', 'In Progress'), # Fixed the typo here
    ('COMPLETED', 'Completed'),
    ('N_A', 'Not Applicable'), # N/A
]

# Choices for MachineToolStatus (if you choose to implement individual tool status tracking)
# If you don't use this, you can remove it.
TOOL_STATUS_CHOICES = [
    ('PENDING', 'Pending Installation'),
    ('INSTALLED', 'Installed'),
    ('FAILED', 'Installation Failed'),
    ('UNINSTALLED', 'Uninstalled'),
]

# --- Model Definitions ---

class ProductivityTool(models.Model):
    """
    Represents a software tool that can be installed on machines.
    """
    name = models.CharField(max_length=255, unique=True, help_text="Name of the productivity tool (e.g., 'Microsoft Office', 'VS Code')")
    description = models.TextField(blank=True, help_text="Detailed description or purpose of the tool.")
    download_link = models.URLField(blank=True, null=True, help_text="URL to download the tool installer.")
    version = models.CharField(max_length=50, blank=True, help_text="Current version of the tool.")
    optional = models.BooleanField(default=False, help_text="Is this tool optional, or is it a default requirement for specific departments?")

    class Meta:
        verbose_name = "Productivity Tool"
        verbose_name_plural = "Productivity Tools"
        ordering = ['name'] # Order tools alphabetically by name

    def __str__(self):
        return self.name

class Department(models.Model):
    """
    Represents a department within the organization, which may have default tools.
    """
    name = models.CharField(max_length=255, unique=True, help_text="Name of the department (e.g., 'Engineering', 'Marketing')")
    description = models.TextField(blank=True, help_text="Description of the department's role.")
    productivity_tools = models.ManyToManyField(
        ProductivityTool,
        blank=True,
        related_name='departments',
        help_text="Default productivity tools required for this department."
    )

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ['name']

    def __str__(self):
        return self.name

class ChecklistItem(models.Model):
    name = models.CharField(max_length=255, unique=True, help_text="Name of the checklist item (e.g., 'Install Antivirus')")
    description = models.TextField(blank=True, help_text="Detailed description of the checklist item.")
    order = models.IntegerField(default=0, help_text="Order in which this item should appear.")
    is_critical = models.BooleanField(default=False, help_text="Is this a critical item for deployment?")

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Checklist Item"
        verbose_name_plural = "Checklist Items"

    def __str__(self):
        return self.name

class Machine(models.Model):
    os = models.CharField(max_length=255, null=True, blank=True)  
    cpu = models.CharField(max_length=255, null=True, blank=True)
    ram = models.CharField(max_length=255, null=True, blank=True)
    mac_address = models.CharField(max_length=255, null=True, blank=True)
    hostname = models.CharField(max_length=255, unique=True, help_text="Network hostname of the machine.")
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP address of the machine (optional).")
    overall_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text="Overall preparation status of the machine."
    )
    assigned_user = models.CharField(max_length=255, blank=True, null=True)
    assignment_date = models.DateTimeField(blank=True, null=True) 
    is_lead = models.BooleanField(default=False, help_text="Is this machine designated as a 'lead' for a task or department?")
    last_checkin = models.DateTimeField(auto_now=True, help_text="Timestamp of the last check-in from the machine agent.")
    department = models.ForeignKey(
        Department, # Directly reference Department model
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='machines',
        help_text="The department this machine is assigned to."
    )
    optional_tools = models.ManyToManyField(
        ProductivityTool,
        blank=True,
        related_name='machines_with_optional_assignment',
        help_text="Optional tools specifically assigned to this machine."
    )
    checklist_items = models.ManyToManyField(
        ChecklistItem,
        through='MachineChecklistStatus', # Specify the intermediate model
        related_name='machines_with_status',
        blank=True,
        help_text="Checklist items associated with this machine and their status."
    )

    class Meta:
        verbose_name = "Machine"
        verbose_name_plural = "Machines"
        ordering = ['hostname'] # Order machines alphabetically by hostname

    def __str__(self):
        return self.hostname
    
    def update_overall_status(self):
        # This is a simplified logic. You'd likely check all required checklist items
        # and productivity tools from the department.
        total_checklist_items = ChecklistItem.objects.count()
        completed_checklist_items = self.machinecheckliststatus_set.filter(status='COMPLETED').count()

        if completed_checklist_items == total_checklist_items and self.department:
            # Also check if all required tools are 'installed' if you track that
            self.overall_status = 'READY'
        elif completed_checklist_items > 0 or self.department:
            self.overall_status = 'IN_PROGRESS'
        else:
            self.overall_status = 'PENDING'
        self.save()

    def save(self, *args, **kwargs):
        is_new_assignment = False
        if self.pk:
            # Fetch original record to detect department change
            try:
                original = Machine.objects.get(pk=self.pk)
                if original.department is None and self.department is not None:
                    is_new_assignment = True
            except Machine.DoesNotExist:
                pass
        elif self.department:
            is_new_assignment = True

        # Set assignment date
        if is_new_assignment and not self.assignment_date:
            self.assignment_date = timezone.now()

        super().save(*args, **kwargs)

        # 🔥 Automatically assign department's tools to this machine
        if is_new_assignment:
            if self.department:
                self.optional_tools.set(self.department.productivity_tools.all())


class MachineChecklistStatus(models.Model):
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="checklist_statuses"
    )
    checklist_item = models.ForeignKey(ChecklistItem, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=CHECKLIST_STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.machine.hostname} - {self.checklist_item.name} - {self.status}"


class MachineToolStatus(models.Model):
    """
    Optional: Tracks the installation status of individual tools on a machine.
    This model is provided as an example if you want more granular tool tracking
    beyond just assignment (optional_tools field).
    If you do not intend to track tool installation status granularly, you can remove this.
    """
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    tool = models.ForeignKey(ProductivityTool, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=TOOL_STATUS_CHOICES, default='PENDING')
    last_checked = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('machine', 'tool')
        verbose_name = "Machine Tool Status"
        verbose_name_plural = "Machine Tool Statuses"

    def __str__(self):
        return f"{self.machine.hostname} - {self.tool.name}: {self.get_status_display()}"
    

class AgentInstallationReport(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='install_reports')
    status = models.CharField(max_length=50, default='completed')
    installed_tools = models.JSONField(default=list, blank=True)
    reported_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.machine.hostname} - {self.status} at {self.reported_at.strftime('%Y-%m-%d %H:%M')}"
