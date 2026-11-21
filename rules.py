SEVERITY_WEIGHTS = {"error": 20, "warning": 7, "info": 0}


def readiness_score(findings):
    penalty = sum(SEVERITY_WEIGHTS.get(item["severity"], 0) for item in findings)
    return max(0, 100 - penalty)


def prioritize(findings):
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(findings, key=lambda item: order.get(item["severity"], 3))


def summarize(findings, score, test_result=None):
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    test_status = test_result["status"] if test_result else "not_run"
    if errors:
        submission_readiness = "Blocked by errors"
    elif test_status == "not_run":
        submission_readiness = "Tests pending"
    elif test_status == "passed":
        submission_readiness = (
            "Ready to submit" if warnings <= 2 else "Review recommended"
        )
    elif test_status == "failed":
        submission_readiness = "Tests failed"
    else:
        submission_readiness = "Review recommended"
    return {
        "readiness_score": score,
        "quality_score": score,
        "errors": errors,
        "warnings": warnings,
        "checks": len(findings),
        "test_status": test_status,
        "submission_readiness": submission_readiness,
        "note": "The score is a heuristic summary, not a guarantee of submission quality.",
    }
