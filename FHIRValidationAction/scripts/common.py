import os
import json

def append_failure(filename, response, failed):
    new_issue = {
        "severity": "failure",
        "diagnostics": f"{response}"
    }
    # If filename doesn't exist yet, create the OperationOutcome shell, then append the issue
    failed.setdefault(filename, {
        "resourceType": "OperationOutcome",
        "issue": []
    })["issue"].append(new_issue)
    return

def dump_json(output_file,issues):
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            existing = json.load(f)
        for filename, outcome in issues.items():
            if filename in existing:
                existing[filename]["issue"].extend(outcome["issue"])
            else:
                existing[filename] = outcome
    else:
        existing = issues

    with open(output_file, 'w') as f:
        json.dump(existing, f, indent=4)
    return