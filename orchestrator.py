from app.agent.rules import prioritize, readiness_score, summarize
from app.analyzers import (
    architecture_analyzer,
    build_analyzer,
    code_analyzer,
    code_review_analyzer,
    dependency_analyzer,
    documentation_analyzer,
    project_analyzer,
    requirements_analyzer,
    security_analyzer,
    test_analyzer,
    traceability_analyzer,
)


def analyze_project(project_path, max_files=1000, max_file_bytes=1024 * 1024):
    findings = []
    agent_runs = []

    def run_agent(name, responsibility, callback):
        try:
            result = callback()
            agent_runs.append({"name": name, "responsibility": responsibility, "status": "completed", "error": None})
            return result
        except Exception as error:
            agent_runs.append({"name": name, "responsibility": responsibility, "status": "failed", "error": str(error)[:500]})
            return None

    project_metadata, project_findings = run_agent(
        "Project Understanding",
        "Detect languages, frameworks, entry points, and configuration.",
        lambda: project_analyzer.analyze(project_path),
    ) or ({}, [])
    findings.extend(project_findings)

    findings.extend(run_agent("Requirements Analysis", "Inspect requirement manifests and project evidence.", lambda: requirements_analyzer.analyze(project_path)) or [])
    findings.extend(run_agent("Code Quality", "Parse Python source and inspect syntax.", lambda: code_analyzer.analyze(project_path, max_files=max_files, max_file_bytes=max_file_bytes)) or [])
    findings.extend(run_agent("Code Review", "Apply static review rules.", lambda: code_review_analyzer.analyze(project_path, max_files=max_files, max_file_bytes=max_file_bytes)) or [])
    findings.extend(run_agent("Dependency Management", "Inspect dependency declarations and constraints.", lambda: dependency_analyzer.analyze(project_path)) or [])
    findings.extend(run_agent("Documentation", "Assess README and license evidence.", lambda: documentation_analyzer.analyze(project_path)) or [])
    findings.extend(run_agent("Automated Testing", "Discover test suites without executing uploaded code.", lambda: test_analyzer.analyze(project_path, max_files=max_files)) or [])
    findings.extend(run_agent("Security Analysis", "Apply local security heuristics.", lambda: security_analyzer.analyze(project_path, max_files=max_files, max_file_bytes=max_file_bytes)) or [])
    findings.extend(run_agent("Build Validation", "Inspect build and container configuration.", lambda: build_analyzer.analyze(project_path)) or [])
    findings.extend(run_agent("Architecture", "Assess source layout and module separation.", lambda: architecture_analyzer.analyze(project_path)) or [])

    traceability_result = run_agent(
        "Requirements Traceability",
        "Map declarations to implementation imports.",
        lambda: traceability_analyzer.analyze(project_path, max_files=max_files, max_file_bytes=max_file_bytes),
    )
    if traceability_result:
        traceability, trace_findings = traceability_result
        findings.extend(trace_findings)
    else:
        traceability = []

    ordered = prioritize(findings)
    score = readiness_score(ordered)
    code_review = [item for item in ordered if item["category"] == "code_review"]
    return {
        "summary": summarize(ordered, score),
        "findings": ordered,
        "traceability": traceability,
        "code_review": code_review,
        "project_metadata": project_metadata,
        "agent_runs": agent_runs,
    }
