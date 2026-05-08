from rest_framework import serializers
from .models import ContractAnalysis, ContractResult


class ContractResultSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ContractResult
        fields = [
            'id', 'row_index', 'contract_id', 'country', 'sector',
            'actual_value', 'predicted_value', 'award_date',
            'risk_score', 'risk_flag', 'missing_fields',
        ]


class ContractAnalysisSerializer(serializers.ModelSerializer):
    results = ContractResultSerializer(many=True, read_only=True)

    class Meta:
        model  = ContractAnalysis
        fields = [
            'id', 'file_name', 'uploaded_at', 'status',
            'total_contracts', 'high_risk_count', 'medium_risk_count',
            'low_risk_count', 'avg_risk_score', 'error_message', 'results',
        ]
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by']


class AnalysisSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer without nested results."""
    class Meta:
        model  = ContractAnalysis
        fields = [
            'id', 'file_name', 'uploaded_at', 'status',
            'total_contracts', 'high_risk_count', 'medium_risk_count',
            'low_risk_count', 'avg_risk_score',
        ]
