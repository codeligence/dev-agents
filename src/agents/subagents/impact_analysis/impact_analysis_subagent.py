"""Impact Analysis Subagent

This subagent orchestrates UI and API impact analysis using CodeResearchAgent
to analyze code changes and determine potential impacts.
"""

import re
from typing import List, Dict, Optional, Union

from core.config import BaseConfig, get_default_config
from core.prompts import BasePrompts, get_default_prompts
from core.log import get_logger
from core.protocols.agent_protocols import AgentExecutionContext
from integrations.git.models import GitDiffContext
from agents.subagents.code_research import create_code_research_agent, CodeResearchDependencies
from .models import ImpactAnalysisResult, UIImpactReport, ApiImpactReport, ImpactAnalysisConfig, ImpactAnalysisPrompts

logger = get_logger(logger_name="ImpactAnalysisSubagent", level="DEBUG")


class ImpactAnalysisSubagent:
    """Subagent for analyzing UI and API impact of code changes.

    Uses CodeResearchAgent instances to analyze frontend and backend changes
    separately and provides comprehensive impact analysis.
    """

    def __init__(self, context: AgentExecutionContext, base_config: BaseConfig = None, base_prompts: BasePrompts = None):
        # Store the execution context
        self.context = context
        
        # Use defaults if not provided
        base_config = base_config or get_default_config()
        base_prompts = base_prompts or get_default_prompts()

        # Create typed wrappers
        self.config = ImpactAnalysisConfig(base_config)
        self.prompts = ImpactAnalysisPrompts(base_prompts)

    def is_frontend_file(self, file_path: str) -> bool:
        """Determine if a file is a frontend file based on its path and extension."""
        frontend_patterns = [
            r'.*\.(js|ts|jsx|tsx)$',  # JavaScript/TypeScript files
            r'.*\.(html|htm)$',  # HTML files
            r'.*\.(css|scss|sass|less)$',  # Style files
            r'.*\.(vue|svelte)$',  # Framework files
            r'.*/src/app/.*',  # Angular app files
            r'.*/components?/.*\.(js|ts|jsx|tsx)$',  # Component files
            r'.*/services?/.*\.(js|ts)$',  # Frontend service files
        ]
        return any(re.match(pattern, file_path, re.IGNORECASE) for pattern in frontend_patterns)

    def is_backend_file(self, file_path: str) -> bool:
        """Determine if a file is a backend file based on its path and extension."""
        backend_patterns = [
            r'.*\.cs$',  # C# files
            r'.*Controller\.cs$',  # Controllers
            r'.*/Models?/.*\.cs$',  # Model files
            r'.*/DTOs?/.*\.cs$',  # DTO files
            r'.*/Contracts?/.*\.cs$',  # Contract files
            r'.*\.csproj$',  # Project files
            r'.*appsettings.*\.json$',  # Configuration files
            r'.*\.sql$',  # SQL files
            r'.*/Services?/.*\.cs$',  # Service files
        ]
        return any(re.match(pattern, file_path, re.IGNORECASE) for pattern in backend_patterns)

    async def _generate_ui_impact_report(self, file_path: str, file_diff: str,
                                       git_diff_context: GitDiffContext) -> UIImpactReport:
        """Generate UI impact report for a single file."""
        try:
            # Create code research agent for UI analysis
            result = await self.execute_research_agent(file_path, file_diff, git_diff_context, 'ui')

            # Parse result into UIImpactReport
            # For now, return a basic report - could be enhanced with more sophisticated parsing
            return UIImpactReport(
                summary=f"UI impact analysis for {file_path}",
                impacted_components=[{
                    "name": f"Components using {file_path}",
                    "file_path": file_path,
                    "component_type": "analysis_result",
                    "dependencies": [],
                    "impact_reason": result[:500] + "..." if len(result) > 500 else result
                }],
                testing_recommendations=[
                    "Review UI components that depend on modified functionality",
                    "Test user interactions with affected components",
                    "Verify data binding and display correctness"
                ],
                risk_assessment="medium"
            )

        except Exception as e:
            logger.error(f"Error generating UI impact report for {file_path}: {e}")
            return UIImpactReport(
                summary=f"Error analyzing {file_path}: {e}",
                impacted_components=[],
                testing_recommendations=["Manual testing recommended due to analysis error"],
                risk_assessment="unknown"
            )

    async def _generate_api_impact_report(self, file_path: str, file_diff: str,
                                        git_diff_context: GitDiffContext) -> ApiImpactReport:
        """Generate API impact report for a single file."""
        try:
            # Create code research agent for API analysis
            result = await self.execute_research_agent(file_path, file_diff, git_diff_context, 'api')

            # Parse result into ApiImpactReport
            # For now, return a basic report - could be enhanced with more sophisticated parsing
            return ApiImpactReport(
                summary=f"API impact analysis for {file_path}",
                api_changes=[{
                    "endpoint_or_method": f"Changes in {file_path}",
                    "change_type": "modified",
                    "file_path": file_path,
                    "impact_description": result[:500] + "..." if len(result) > 500 else result,
                    "breaking_change": False
                }],
                breaking_changes=[],
                integration_risks=[
                    "Review integration points that use modified functionality",
                    "Verify backward compatibility"
                ],
                testing_recommendations=[
                    "Test API endpoints that may be affected",
                    "Verify response schemas and contracts",
                    "Check integration with dependent services"
                ],
                risk_assessment="medium"
            )

        except Exception as e:
            logger.error(f"Error generating API impact report for {file_path}: {e}")
            return ApiImpactReport(
                summary=f"Error analyzing {file_path}: {e}",
                api_changes=[],
                breaking_changes=[],
                integration_risks=["Manual testing recommended due to analysis error"],
                testing_recommendations=["Manual API testing recommended"],
                risk_assessment="unknown"
            )

    async def execute_research_agent(self, file_path: str, file_diff: str, git_diff_context: GitDiffContext, analysis_type: str) -> str:
        """Execute research agent for impact analysis.

        Args:
            file_path: Path to the changed file
            file_diff: Diff content of the file
            git_diff_context: Git diff context containing repo path, branch info, and work item context
            analysis_type: 'ui' for UI analysis, 'api' for API analysis

        Returns:
            Analysis result as string
        """
        # Get configuration values
        model = self.config.get_code_research_model()
        num_retries = self.config.get_num_retries()

        # Get the appropriate system prompt
        if analysis_type == 'ui':
            system_prompt = self.prompts.get_ui_impact_prompt()
        else:  # api
            system_prompt = self.prompts.get_api_impact_prompt()

        # Create research agent
        agent = create_code_research_agent(
            model=model,
            system_prompt=system_prompt,
            num_retries=num_retries
        )

        # Prepare dependencies
        deps = CodeResearchDependencies(
            git_ref=git_diff_context.source_branch,
            repo_path=git_diff_context.repo_path
        )

        # Create analysis prompt using template
        prompt_template = self.prompts.get_file_instruction_prompt()
        prompt = prompt_template.format(
            file_path=file_path,
            issue_context=git_diff_context.context,
            file_diff=file_diff
        )

        # Run the analysis
        result = await agent.run(prompt, deps=deps)
        return result.output

    async def _process_files_with_progress(
        self, 
        files_to_process: List[str], 
        git_diff_context: GitDiffContext,
        analysis_function,
        report_list: List,
        file_type_name: str,
        processed_files: List[str],
        total_files: int
    ) -> None:
        """Process files with progress updates in a DRY manner.
        
        Args:
            files_to_process: List of file paths to process
            git_diff_context: Git diff context containing file diffs
            analysis_function: Function to call for analysis (_generate_ui_impact_report or _generate_api_impact_report)
            report_list: List to append results to (ui_reports or api_reports)
            file_type_name: Name for logging (e.g., "frontend", "backend")
            processed_files: List to track processed files (modified in-place)
            total_files: Total number of files that will be processed for progress calculation
        """
        for file_path in files_to_process:
            if len(processed_files) >= self.config.get_max_files():
                break

            try:
                # Send progress update
                current_index = len(processed_files) + 1
                await self.context.send_status(f"🔎 {current_index}/{total_files}: {file_path}")
                
                logger.debug(f"Analyzing {file_type_name} file {current_index}: {file_path}")
                file_diff = git_diff_context.file_diffs[file_path]

                report = await analysis_function(
                    file_path=file_path,
                    file_diff=file_diff,
                    git_diff_context=git_diff_context
                )

                report_list.append(report)
                processed_files.append(file_path)

                logger.debug(f"Successfully analyzed {file_type_name} file: {file_path}")

            except Exception as e:
                logger.error(f"Error analyzing {file_type_name} file {file_path}: {e}")

    async def run(self, git_diff_context: GitDiffContext) -> ImpactAnalysisResult:
        """Run impact analysis on the provided git diff context.

        Args:
            git_diff_context: GitDiffContext containing file diffs and metadata

        Returns:
            ImpactAnalysisResult with UI and API impact analysis
        """
        logger.debug(f"Starting impact analysis for {len(git_diff_context.file_diffs)} files")

        # Categorize files
        frontend_files = []
        backend_files = []
        other_files = []

        for file_path in git_diff_context.file_diffs.keys():
            if self.is_frontend_file(file_path):
                frontend_files.append(file_path)
            elif self.is_backend_file(file_path):
                backend_files.append(file_path)
            else:
                other_files.append(file_path)

        # Calculate total files that will be processed for accurate progress tracking
        max_files = self.config.get_max_files()
        total_files_available = len(frontend_files) + len(backend_files)
        total_files_to_process = min(total_files_available, max_files)

        logger.debug(f"Categorized files: {len(frontend_files)} frontend, {len(backend_files)} backend, {len(other_files)} other. Analyzing max {max_files} files (total: {total_files_to_process}).")

        # Initialize results
        ui_reports = []
        api_reports = []
        processed_files = []

        # Process frontend files with progress updates
        await self._process_files_with_progress(
            files_to_process=frontend_files,
            git_diff_context=git_diff_context,
            analysis_function=self._generate_ui_impact_report,
            report_list=ui_reports,
            file_type_name="frontend",
            processed_files=processed_files,
            total_files=total_files_to_process
        )

        # Process backend files with progress updates  
        await self._process_files_with_progress(
            files_to_process=backend_files,
            git_diff_context=git_diff_context,
            analysis_function=self._generate_api_impact_report,
            report_list=api_reports,
            file_type_name="backend",
            processed_files=processed_files,
            total_files=total_files_to_process
        )

        # Create result
        result = ImpactAnalysisResult(
            ui_impacts=ui_reports,
            api_impacts=api_reports
        )

        logger.debug(f"Impact analysis complete: UI reports: {len(ui_reports)}, API reports: {len(api_reports)}")
        return result
