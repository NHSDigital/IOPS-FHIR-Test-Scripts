'''This script is ued to test FHIR validation on the server. It will send a request to the server and check if the response is valid according to the FHIR specification.
Input: FHIR resource instance in JSOn or XML
- pass filename format: [resourceType]-[any].[json|xml]
- fail filename format: [resourceType]-[element to error on].[json|xml]

Output: validation results
- pass files: passes with no errors
- fail files: 
- - pass if single error returned where the error message contains element to error on
- - fails if no errors or multiple errors are returned

Authentication to the server is done outside this script
'''

from logging import config
import os
import json
import requests
from dotenv import load_dotenv
import xml.etree.ElementTree as ET



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

def get_json_info(file_path):
    try:
        with open(file_path, encoding='utf-8') as f:
            resource = json.load(f)
        
        resource_type = resource.get('resourceType')
        resource_id = resource.get('id')

        return resource, resource_id, resource_type
    
    except Exception as e:
        print(f"Error getting resource id and resource type for {str(file_path)}: {e}")
        return False

def get_xml_info(file_path):
    try:
        # Parse just to extract id and resourceType
        tree = ET.parse(file_path)
        root = tree.getroot()
    
        NS = "{http://hl7.org/fhir}"
        resource_type = root.tag.replace(NS, "")
        
        id_element = root.find(f"{NS}id")
        resource_id = id_element.get("value")

        # Read raw bytes instead of re-serialising via ET
        with open(file_path, 'rb') as f:
            resource = f.read()

        return resource, resource_id, resource_type
    
    except Exception as e:
        print(f"Error getting resource id and/or resource type for {file_path}: {e}")
        return False

def validate_resource(file_path, resource, resource_id, resource_type, format, operation_outcomes, TOKEN):
    try:
        url = f"{SERVER_URL}/{resource_type}/$validate"
        headers = {"Accept": "application/fhir+json"}
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
        
        if format == "xml":
            headers["Content-Type"] = "application/fhir+xml;charset=utf-8"
            response = requests.post(
                url,
                data=resource,  # raw XML string of the resource
                headers=headers
            )
        else:
            headers["Content-Type"] = "application/fhir+json"
            params = {
                "resourceType": "Parameters",
                "parameter": [
                    {
                        "name": "resource",
                        "resource": resource
                    }
                ]
            }
            response = requests.post(
                url,
                json=params,
                headers=headers
            )

        # $validate always returns an OperationOutcome
        outcome = response.json()
        operation_outcomes.update({str(file_path):outcome})
        print(f"Validated {resource_type}/{resource_id}")
        return True

    except Exception as e:
        print(f"Error validating {str(file_path)}: {e}")
        return False
    

def test_endpoint(url, TOKEN):
    
    headers = {
        "Accept": "application/json"
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"


    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        status_dict = {200: "Success", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found", 500: "Internal Server Error"}

        if response.status_code in status_dict:
            status_text = status_dict[response.status_code]
            print(f"Server responded with status code {response.status_code}: {status_text}")
        else:
            print(f"Server responded with status code {response.status_code}")
        return response.status_code

    except requests.exceptions.RequestException as e:
        print(f"Error testing endpoint {url}: {e}")
        return
    
def main_validation():
    try:
        os.remove("operational-outcomes.json") 
    except:
        pass

    TOKEN = os.getenv("BEARER_TOKEN")
    with open("config.json", "r") as f:
        config = json.load(f)
    url = config["server"]
    print(url)
    
    if test_endpoint(url, TOKEN) == 200:
        all_operational_outcomes = {}
        
        for val_type, folder in config["paths"].items():
            operation_outcomes = {}
            for root, dirs, files in os.walk(folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    format = "json" if file.endswith("json") else "xml"
                    get_info = get_json_info if format == "json" else get_xml_info
                    result = get_info(file_path)
                    if result is False:
                        continue
                    resource, resource_id, resource_type = result
                    validate_resource(file_path, resource, resource_id, resource_type, format, operation_outcomes)
        
        all_operational_outcomes[val_type] = operation_outcomes
        dump_json(f"operation_outcome_{val_type}.json", f"operation_outcomes_{val_type}")
    try:
        return all_operational_outcomes
    except:
        return {}

if __name__ == "__main__":
    all_operational_outcomes = main_validation()

    for key, operational_outcomes in all_operational_outcomes.items():
        print(f"Results for {key} files:")
        if key == "pass":
            for filename, issues in operational_outcomes.items():
                fails = [issue for issue in issues if issue["severity"] == "error"]
                if not fails:
                    print(f"{filename} passed validation with no issues.")
                else:
                    print(f"{filename} failed validation with issues:")
                    for issue in fails:
                            print(f"\n\t- {issue['diagnostics']}")
        
        elif key == "fail":
            for filename, issues in operational_outcomes.items():
                fails = []
                passes = []
                for issue in issues:
                    if any(element in issue["diagnostics"] for element in filename.split("-")[1:]):
                        passes.append(issue)
                    else:
                        fails.append(issue)
                if fails or not passes:
                    print(f"{filename} failed validation with issues:")
                    if fails:
                        print(f"{filename} failed validation with other issues: {fails[0]['diagnostics']}")
                    if len(passes) == 0:
                        print(f"{filename} expected to fail on {filename.split('-')[1]}, but did not fail on that element.")
                else:
                    print(f"{filename} passed validation with no issues.")
                        