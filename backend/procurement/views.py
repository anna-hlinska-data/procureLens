import io
import sys
import os
import pandas as pd
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import ContractAnalysis, ContractResult
from .serializers import ContractAnalysisSerializer, AnalysisSummarySerializer

# Add frontend to path so we can import risk_engine
FRONTEND_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend')
if FRONTEND_PATH not in sys.path:
    sys.path.insert(0, os.path.abspath(FRONTEND_PATH))


def _run_pipeline(file_obj, filename: str) -> tuple[pd.DataFrame, dict]:
    """
    Run the full data pipeline on an uploaded file.
    Returns (risk_df, summary_stats)
    """
    from csv_converter import convert_to_csv, FileTypeFlags
    from cleaning import clean_data
    from mapping import prepare_headers
    from risk_engine import analyse_contracts, risk_summary

    # Save file temporarily
    import tempfile, shutil
    suffix = os.path.splitext(filename)[1] or '.csv'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file_obj, tmp)
        tmp_path = tmp.name

    try:
        # 1. Convert to CSV
        csv_path = convert_to_csv(tmp_path)
        if csv_path is None:
            raise ValueError("File conversion failed — no table found")

        # 2. Read + map headers
        df = pd.read_csv(csv_path)
        df = prepare_headers(df)

        # 3. Clean
        cleaned_df = clean_data(df)

        # 4. Risk analysis
        risk_df = analyse_contracts(cleaned_df)
        stats   = risk_summary(risk_df)

        return risk_df, stats

    finally:
        os.unlink(tmp_path)


@extend_schema(
    summary="Upload and analyse a procurement file",
    description="Upload CSV/Excel/PDF. Returns risk analysis results.",
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_contracts(request):
    """
    POST /api/v1/procurement/upload/
    Multipart form: file=<procurement file>
    """
    if 'file' not in request.FILES:
        return Response(
            {'error': 'No file provided. Use multipart field "file".'},
            status=status.HTTP_400_BAD_REQUEST
        )

    uploaded_file = request.FILES['file']
    filename      = uploaded_file.name

    # Create analysis record
    analysis = ContractAnalysis.objects.create(
        uploaded_by=request.user,
        file_name=filename,
        status='processing',
    )

    try:
        risk_df, stats = _run_pipeline(uploaded_file, filename)

        # Update analysis record
        analysis.total_contracts   = stats.get('total', 0)
        analysis.high_risk_count   = stats.get('high_risk', 0)
        analysis.medium_risk_count = stats.get('medium_risk', 0)
        analysis.low_risk_count    = stats.get('low_risk', 0)
        analysis.avg_risk_score    = stats.get('avg_risk_score', 0.0)
        analysis.status            = 'completed'
        analysis.save()

        # Save individual contract results (up to 1000 rows)
        results_to_create = []
        for idx, row in risk_df.head(1000).iterrows():
            flag_raw = str(row.get('risk_flag', '🟢 LOW'))
            if 'HIGH' in flag_raw:
                flag = 'HIGH'
            elif 'MEDIUM' in flag_raw:
                flag = 'MEDIUM'
            else:
                flag = 'LOW'

            # detect column names flexibly
            def get_val(keys):
                for k in keys:
                    if k in row.index and pd.notna(row[k]):
                        return row[k]
                return None

            results_to_create.append(ContractResult(
                analysis        = analysis,
                row_index       = int(idx),
                contract_id     = str(get_val(['transaction_id','contract_id','id']) or '')[:255],
                country         = str(get_val(['company','country','iso_country_code']) or '')[:100],
                sector          = str(get_val(['item_category','cpv_sector','sector']) or '')[:255],
                actual_value    = float(get_val(['total_cost','contract_value_eur','unit_price']) or 0),
                predicted_value = float(row.get('predicted_value_eur', 0) or 0),
                award_date      = str(get_val(['purchase_date','award_date']) or '')[:50],
                risk_score      = float(row.get('risk_score', 0) or 0),
                risk_flag       = flag,
                missing_fields  = int(row.get('missing_critical_fields', 0) or 0),
            ))

        ContractResult.objects.bulk_create(results_to_create)

        serializer = ContractAnalysisSerializer(analysis)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    except Exception as e:
        analysis.status        = 'failed'
        analysis.error_message = str(e)
        analysis.save()
        return Response(
            {'error': str(e), 'analysis_id': str(analysis.id)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(summary="List all analyses for current user")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_analyses(request):
    """GET /api/v1/procurement/analyses/"""
    analyses = ContractAnalysis.objects.filter(uploaded_by=request.user)
    serializer = AnalysisSummarySerializer(analyses, many=True)
    return Response(serializer.data)


@extend_schema(summary="Get full analysis results by ID")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_analysis(request, analysis_id):
    """GET /api/v1/procurement/analyses/<analysis_id>/"""
    try:
        analysis = ContractAnalysis.objects.get(
            id=analysis_id,
            uploaded_by=request.user
        )
    except ContractAnalysis.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ContractAnalysisSerializer(analysis)
    return Response(serializer.data)


@extend_schema(summary="Get only high-risk contracts from an analysis")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_high_risk(request, analysis_id):
    """GET /api/v1/procurement/analyses/<analysis_id>/high-risk/"""
    try:
        analysis = ContractAnalysis.objects.get(
            id=analysis_id,
            uploaded_by=request.user
        )
    except ContractAnalysis.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    high_risk = analysis.results.filter(risk_flag='HIGH')
    from .serializers import ContractResultSerializer
    serializer = ContractResultSerializer(high_risk, many=True)
    return Response({
        'analysis_id':    str(analysis_id),
        'high_risk_count': high_risk.count(),
        'results':        serializer.data,
    })
