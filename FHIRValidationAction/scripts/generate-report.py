import os
import json
from collections import defaultdict
import yaml
from pathlib import Path
import sys

#for local testing
#ROOT = Path.cwd() / "FHIRValidationAction"

#for github repo
ROOT = Path.cwd() / "validation" / "FHIRValidationAction"

def parse_validation_output(results_file, ignore_list):
    
    
    issues = {"fatal": [], "error": [], "warning": [], "information": [], "failure": [], "passed": []}
    
    for file_path, outcome in results_file.items():
        for issue in outcome.get("issue", []):
            severity = issue.get("severity", "").lower()
            diagnostics = issue.get("diagnostics", "")

            if "No issues detected during validation" in diagnostics:
                severity = "passed"
            
            if is_ignored(issue, ignore_list, severity, diagnostics):
                severity = "passed"
            # expression and location are both lists of strings
            expression = issue.get("expression", [])
            location = issue.get("location", [])
            
            # Get line/col from extensions if available
            line, col = None, None
            for ext in issue.get("extension", []):
                if "issue-line" in ext.get("url", ""):
                    line = ext.get("valueInteger")
                elif "issue-col" in ext.get("url", ""):
                    col = ext.get("valueInteger")
            
            position = f"Line[{line}] Col[{col}]" if line and col else ", ".join(location)

            if severity in issues:
                issues[severity].append({
                    "file": file_path,
                    "message": diagnostics,
                    "expression": ", ".join(expression),
                    "location": position
                })
    
    return issues

def is_ignored(issue, ignore_config, severity, diagnostics):
  
    # Get the list for this severity, default to empty list if None/missing
    rules = ignore_config.get("ignore-list", {}).get(severity) or []
    
    return any(string in diagnostics for string in rules)

def group_by_file(issue_list):
    grouped = defaultdict(list)
    for issue in issue_list:
        grouped[issue["file"]].append(issue)
    return grouped

def make_file_link(file_path):
    """Create a GitHub link to the file in the repo"""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    if repo and sha:
        # Strip the runner workspace prefix to get a repo-relative path
        workspace = os.environ.get("GITHUB_WORKSPACE", "")
        if workspace and file_path.startswith(workspace):
            file_path = file_path[len(workspace):].lstrip("/")
        url = f"https://github.com/{repo}/blob/{sha}/{file_path}"
        return f'<a href="{url}"><code>{file_path}</code></a>'
    return f"<code>{file_path}</code>"

def render_section(title, emoji, issues, colour):
    grouped = group_by_file(issues)
    total = len(issues)
    file_count = len(grouped)

    html = f"""
<details>
<summary><strong>{emoji} {title} &nbsp;|&nbsp; {total} total across {file_count} file(s)</strong></summary>
<br>
"""

    if not issues:
        html += f"<p>✅ No {title.lower()} found.</p>\n"
    else:
        for file_path, file_issues in sorted(grouped.items()):
            html += f"<details>\n<summary>{make_file_link(file_path)} &nbsp;— {len(file_issues)} {title.lower()}</summary>\n<br>\n"
            html += '<table><thead><tr><th>Location</th><th>Message</th></tr></thead><tbody>\n'
            for issue in file_issues:
                location = issue.get("location") or "—"
                message = issue["message"]
                html += f"<tr><td><code>{location}</code></td><td>{message}</td></tr>\n"
            html += "</tbody></table>\n</details>\n<br>\n"

    html += "</details>\n"
    return html



def main():
    with open(f"{ROOT}/scripts/ignore-list.yaml", "r") as f:
            ignore_list = yaml.safe_load(f)
    
    try:
        with open(f"{ROOT}/operation_outcomes.json") as f:
            results_file = json.load(f)    
    except:
        print("No operation_outcomes.json found. Skipping generating report")
        return 0

    issues = parse_validation_output(results_file, ignore_list)
    failures = issues["failure"]
    fatals = issues["fatal"]
    errors = issues["error"]
    warnings = issues["warning"]
    information = issues["information"]
    passes = issues["passed"]
    summary = f"""# 🏥 FHIR Validation Summary

| Severity | Count |
|----------|-------|
| ⚠️ Failed Uploads | {len(failures)} |
| ❗ Fatals | {len(fatals)} |
| 🔴 Errors | {len(errors)} |
| 🟡 Warnings | {len(warnings)} |
| 🔵 Information | {len(information)} |
| 🟢 Passes (incl. hidden issues) | {len(passes)} |

---
{render_section("Failed Uploads", "⚠️", failures, "red")}

{render_section("Fatals", "❗", fatals, "red")}

{render_section("Errors", "🔴", errors, "red")}

{render_section("Warnings", "🟡", warnings, "yellow")}

{render_section("Information", "🔵", information, "blue")}

{render_section("Passes", "🟢", passes, "green")}
"""

    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "w") as f:
            f.write(summary)
        print("✅ Summary written to GitHub Actions.")
    else:
        print(summary)
    
    
    filepath = f"{ROOT}/operation_outcomes.json"
    if os.path.exists(filepath):
        os.remove(filepath)
    
    major_issues = len(failures)+len(fatals)+len(errors)
    if major_issues > 0:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
    
