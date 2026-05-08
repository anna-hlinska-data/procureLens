from django.urls import path
from . import views

urlpatterns = [
    path('upload/',                          views.upload_contracts, name='upload-contracts'),
    path('analyses/',                        views.list_analyses,    name='list-analyses'),
    path('analyses/<uuid:analysis_id>/',     views.get_analysis,     name='get-analysis'),
    path('analyses/<uuid:analysis_id>/high-risk/', views.get_high_risk, name='get-high-risk'),
]
