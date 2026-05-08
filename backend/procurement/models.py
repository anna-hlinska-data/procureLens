from django.db import models
from django.utils import timezone
import uuid


class ContractAnalysis(models.Model):
    """Stores each procurement file analysis session."""

    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('completed',  'Completed'),
        ('failed',     'Failed'),
    ]

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by   = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='analyses'
    )
    file_name     = models.CharField(max_length=255)
    uploaded_at   = models.DateTimeField(default=timezone.now)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Summary stats
    total_contracts  = models.IntegerField(default=0)
    high_risk_count  = models.IntegerField(default=0)
    medium_risk_count= models.IntegerField(default=0)
    low_risk_count   = models.IntegerField(default=0)
    avg_risk_score   = models.FloatField(default=0.0)

    error_message = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'procurement_analysis'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.file_name} — {self.status} ({self.uploaded_at.date()})"


class ContractResult(models.Model):
    """Individual contract risk result within an analysis."""

    RISK_CHOICES = [
        ('HIGH',   '🔴 High'),
        ('MEDIUM', '🟡 Medium'),
        ('LOW',    '🟢 Low'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis        = models.ForeignKey(
        ContractAnalysis,
        on_delete=models.CASCADE,
        related_name='results'
    )
    row_index       = models.IntegerField()

    # Contract fields
    contract_id     = models.CharField(max_length=255, blank=True, null=True)
    country         = models.CharField(max_length=100, blank=True, null=True)
    sector          = models.CharField(max_length=255, blank=True, null=True)
    actual_value    = models.FloatField(null=True, blank=True)
    predicted_value = models.FloatField(null=True, blank=True)
    award_date      = models.CharField(max_length=50, blank=True, null=True)

    # Risk output
    risk_score      = models.FloatField(default=0.0)
    risk_flag       = models.CharField(max_length=10, choices=RISK_CHOICES, default='LOW')
    missing_fields  = models.IntegerField(default=0)

    class Meta:
        db_table = 'procurement_result'
        ordering = ['-risk_score']

    def __str__(self):
        return f"{self.contract_id or 'Unknown'} — {self.risk_flag} ({self.risk_score:.3f})"
