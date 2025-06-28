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
    """
    Represents a single task in the machine preparation checklist.
    """
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
    """
    Represents a single machine/workstation being prepared.
    """
    hostname = models.CharField(max_length=255, unique=True, help_text="Network hostname of the machine.")
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP address of the machine (optional).")
    overall_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text="Overall preparation status of the machine."
    )
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

class MachineChecklistStatus(models.Model):
    """
    Intermediate model to track the status of each ChecklistItem for a specific Machine.
    """
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='checklist_statuses')
    checklist_item = models.ForeignKey(ChecklistItem, on_delete=models.CASCADE, related_name='machine_statuses')
    status = models.CharField(
        max_length=20,
        choices=CHECKLIST_STATUS_CHOICES,
        default='PENDING',
        help_text="Current status of this checklist item for the machine."
    )
    notes = models.TextField(blank=True, help_text="Any notes related to this item's status.")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('machine', 'checklist_item') # A machine can only have one status per item
        verbose_name = "Machine Checklist Status"
        verbose_name_plural = "Machine Checklist Statuses"
        ordering = ['checklist_item__order'] # Order by the checklist item's defined order

    def __str__(self):
        return f"{self.machine.hostname} - {self.checklist_item.name}: {self.get_status_display()}"


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
    last_checked = models.DateTimeField(auto_now_add=True) # Or auto_now=True if it updates on every check

    class Meta:
        unique_together = ('machine', 'tool') # A machine can only have one status per tool
        verbose_name = "Machine Tool Status"
        verbose_name_plural = "Machine Tool Statuses"

    def __str__(self):
        return f"{self.machine.hostname} - {self.tool.name}: {self.get_status_display()}"