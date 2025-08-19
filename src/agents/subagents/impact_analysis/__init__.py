"""Impact Analysis Subagent

This subagent analyzes code changes to determine potential UI and API impacts.
It uses CodeResearchAgent instances to analyze frontend and backend changes separately.
"""

from .models import (
    UIComponent,
    UIImpactReport, 
    ApiChange,
    ApiImpactReport,
    ImpactAnalysisResult
)
from .impact_analysis_subagent import ImpactAnalysisSubagent

__all__ = [
    'UIComponent',
    'UIImpactReport',
    'ApiChange', 
    'ApiImpactReport',
    'ImpactAnalysisResult',
    'ImpactAnalysisSubagent'
]