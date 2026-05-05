#!/usr/bin/env python3
"""Upload FHIR conformance resources (StructureDefinitions, ValueSets, CodeSystems, etc.)"""

import json
import requests
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
import os
from common import append_failure, dump_json

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "config.json")

with open(config_path,"r") as f:
    config = json.load(f)
#ROOT = './test' #used for local testing
ROOT = Path.cwd() #used for github actions
SERVER_URL = config["fhir-validator"]["base_url"]

IGNORE_FOLDERS = {"validation", "validation-service-fhir-r4"}

ASSETS_FOLDERS = [
    "CapabilityStatement",
    "StructureDefinition",
    "ImplementationGuide",
    "SearchParameter",
    "MessageDefinition",
    "OperationDefinition",
    "CompartmentDefinition",
    "StructureMap",
    "GraphDefinition",
    "ExampleScenario",
    "CodeSystem",
    "ValueSet",
    "ConceptMap",
    "NamingSystem",
    "TerminologyCapabilities",
    "Conformance-resources"
]
EXAMPLES_FOLDERS = ["Examples"]


def get_json_info(file_path, failed):
    try:
        with open(file_path) as f:
            resource = json.load(f)
        
        resource_type = resource.get('resourceType')
        resource_id = resource.get('id')

        return resource, resource_id, resource_type
    
    except Exception as e:
        print(f"Error getting resource id and resource type for {str(file_path)}: {e}")
        append_failure(str(file_path), e, failed)
        return False

def get_xml_info(file_path, failed):
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
        append_failure(str(file_path), str(e), failed)
        return False

def upload_resource(file_path,resource, resource_id, resource_type, format, failed):
    """Upload a single FHIR resource"""
    try:
        # Use PUT with id for idempotency
        url = f"{SERVER_URL}/{resource_type}/{resource_id}"
        if format == "xml":
            response = requests.put(
                url,
                data=resource,
                headers={
                    "Content-Type": "application/fhir+xml;charset=utf-8",
                    "Accept": "application/fhir+json"
                    }
            )
        else:
            response = requests.put(
                url,
                json=resource,
                headers={
                    "Content-Type": "application/fhir+json",
                    "Accept": "application/fhir+json"}
            )

        
        if response.status_code in [200, 201]:
            print(f"Uploaded {resource_type}/{resource_id}")
            return True
        else:
            print(f"Failed to upload {resource_type}/{resource_id}: {response.status_code}")
            print(f"  File: {str(file_path)}")
            print(f"  Response: {response.text}")
            append_failure(str(file_path), f"{response.status_code}: {response.text}", failed)
            return False
            
    except Exception as e:
        print(f"Error uploading {str(file_path)}: {e}")
        append_failure(str(file_path), str(e), failed)
        return False
    
def validate_resource(file_path, resource, resource_id, resource_type, format, operation_outcomes, failed):
    try:
        url = f"{SERVER_URL}/{resource_type}/$validate"

        if format == "xml":
            response = requests.post(
                url,
                data=resource,  # raw XML string of the resource
                headers={
                    "Content-Type": "application/fhir+xml;charset=utf-8",
                    "Accept": "application/fhir+json"
                    }
            )
        else:
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
                headers={
                    "Content-Type": "application/fhir+json",
                    "Accept": "application/fhir+json"
                    }
            )

        # $validate always returns an OperationOutcome
        outcome = response.json()
        operation_outcomes.update({str(file_path):outcome})

        return True

    except Exception as e:
        print(f"Error validating {str(file_path)}: {e}")
        append_failure(str(file_path), str(e), failed)
        return False




def main():
    failed = {}
    total_num_files = 0
    operation_outcomes = {}

    asset_json_files = set()
    asset_xml_files = set()
    example_json_files = set()
    example_xml_files = set()

    # find all folders that contain string in ASSET_FOLDERS and EXAMPLES and then find all xml/json files within them recursively
    for folder in Path(ROOT).iterdir():
        if folder.is_dir() and folder.name in IGNORE_FOLDERS:
            continue

        if folder.is_dir() and any(asset.lower() in folder.name.lower() for asset in ASSETS_FOLDERS):
            print(f"{folder} found. Gathering assets")
            asset_json_files.update(folder.rglob("*.json"))
            asset_xml_files.update(folder.rglob("*.xml"))
        
        if folder.is_dir() and any(asset.lower() in folder.name.lower() for asset in EXAMPLES_FOLDERS):
            print(f"{folder} found. Gathering examples")
            example_json_files.update(folder.rglob("*.json"))
            example_xml_files.update(folder.rglob("*.xml"))

    # Convert back to list if needed
    asset_json_files = list(asset_json_files)
    asset_xml_files = list(asset_xml_files)
    example_json_files = list(example_json_files)
    example_xml_files = list(example_xml_files)
            
    all_asset_files = [(f, "json") for f in sorted(asset_json_files)] + [(f, "xml") for f in sorted(asset_xml_files)]
    all_example_files = [(f, "json") for f in sorted(example_json_files)] + [(f, "xml") for f in sorted(example_xml_files)]
    all_files = all_asset_files + all_example_files
    total_num_files += len(all_files)
            
    if len(all_files) == 0:
        return 0

    print(f"Uploading {len(all_asset_files)} FHIR assets and {len(all_example_files)} FHIR examples...")
                    
            
    for file_path, format in all_asset_files:
        get_info = get_json_info if format == "json" else get_xml_info
        result = get_info(file_path, failed)
        
        if result is False:
            total_num_files -= 1
            continue
        
        resource, resource_id, resource_type = result
        

        if not upload_resource(file_path, resource, resource_id, resource_type, format, failed):
            total_num_files -= 1
            continue



    for file_path, format in all_files:
        get_info = get_json_info if format == "json" else get_xml_info
        result = get_info(file_path, failed)
        
        if result is False:
            continue
        
        resource, resource_id, resource_type = result

        validate_resource(file_path, resource, resource_id, resource_type, format, operation_outcomes, failed)
    
    dump_json('operation_outcomes.json',failed)
    dump_json('operation_outcomes.json',operation_outcomes)

  
    if failed:
        print(f"\nFailed to upload {len(failed)} assets / examples:")
        for f in failed:
            print(f"  - {f}")
    print(f"\nSuccessfully uploaded {len(all_asset_files)} FHIR assets and {len(all_example_files)} FHIR examples")
    return 0

if __name__ == "__main__":
    sys.exit(main())
 