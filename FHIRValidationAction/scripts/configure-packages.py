#!/usr/bin/env python3
"""Install FHIR package dependencies from package.json"""

import json
import requests
import sys
import time
import os
import base64
from common import append_failure, dump_json
from pathlib import Path
from ruamel.yaml import YAML


script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "config.json")

#for github actions
test_script_repo_path = f"{Path.cwd()}/validation/FHIRValidationAction"
package_path = f"{Path.cwd()}"
application_yaml = "./validation-service-fhir-r4/hapi.application.yaml"


#for testing locally
#test_script_repo_path = "./FHIRValidationAction" 
#package_path = "./FHIRValidationAction/test"
#application_yaml = "../FHIR-Validation/hapi.application.yaml"

with open(config_path,"r") as f:
    config = json.load(f)
SERVER_URL = config["fhir-validator"]["base_url"]

def add_packages_to_application_yaml(source_json, target_yaml=application_yaml):
    yaml = YAML()
    yaml.preserve_quotes = True

    package_dependencies = get_package_dependencies(source_json)    
     
    if not package_dependencies:
        print("No dependencies found in package.json")
        return 0
    
    print(f"Adding FHIR packages for installation...")
    
    with open(application_yaml, "r") as f:
        data = yaml.load(f)
    
    for package_name, version in package_dependencies.items():
        print(f'\tAdding {package_name} : {version}')
        package_key = package_name.replace('.', '-')

        package_entry = {
            'name': package_name,
            'version': version,
            'installMode': 'STORE_AND_INSTALL'
        }

        data['hapi']['fhir']['implementationguides'][package_key] = package_entry

    with open(application_yaml, "w") as f:
        yaml.dump(data, f)
    return 0

def add_private_packages_to_application_yaml(source_yaml, target_yaml=application_yaml):
    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        with open(source_yaml, "r") as f:
            source = yaml.load(f)
    except FileNotFoundError:
        print("No private.package.yaml found - skipping private package installation")
        return 0


    with open(target_yaml, "r") as f:
        target = yaml.load(f)

    print(f"Adding private FHIR packages for installation...")
    # Merge the implementationguides from source into target
    source_guides = source.get('implementationguides', {})
    target_guides = target['hapi']['fhir']['implementationguides']

    for key, value in source_guides.items():
        print(f'\tAdding {value['name']} : {value['version']}')
        value['installMode'] = 'STORE_AND_INSTALL'
        target_guides[key] = value

    with open(target_yaml, "w") as f:
        yaml.dump(target, f)
    return

def get_package_dependencies(package_path):
    try:       
        with open(f"{package_path}/package.json") as f:
            package = json.load(f)
            package_dependencies = package.get('dependencies', {})
            return package_dependencies
    except FileNotFoundError:
        print("No package.json found - skipping package installation")
        return 0

def install_packages_from_json(package_json,failed):
    package_dependencies = get_package_dependencies(package_json)    
     
    if not package_dependencies:
        print("No dependencies found in package.json")
        return 0
    
    print(f"Installing FHIR packages...")
    

    for package_id, version in package_dependencies.items():
        # Give server time between installations
        if package_id == "hl7.fhir.r4.core":
            continue  # Skip core package since it's already on the server
        time.sleep(2)
        print(f"\tInstalling {package_id}:{version}")
        
        if not check_package_locally(package_id, version):
            if not download_package(package_id, version, failed):
                continue

        install_package(package_id, version, SERVER_URL, failed)
        return 

def check_package_locally(package_id, version):
    name = f"{package_id}-{version}.tgz"
    for _, _, files in os.walk(f"{test_script_repo_path}/packages"):
        if name in files:
            return True
    return False

    
def download_package(package_id, version, failed):
    url = f"https://packages.simplifier.net/{package_id}/{version}"
    response = requests.get(url)
    
    if response.status_code == 404:
        print(f"Package {package_id}#{version} not found on registry")
        append_failure("package.json", f"failed to find {package_id}: {version} on FHIR package Registry: {response.status_code} - {response.text}", failed)
        return False
    
    with open(f"{test_script_repo_path}/packages/{package_id}-{version}.tgz", "wb") as f:
        f.write(response.content)
        return True
        
    
def install_package(package_name, version, server_url, failed):
    package_path = f"{test_script_repo_path}/packages/{package_name}-{version}.tgz"
    
    with open(package_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    params = {
        "resourceType": "Parameters",
        "parameter": [
            {"name": "npmContent", "valueBase64Binary": encoded},
            {"name": "installMode", "valueCode": "STORE_AND_INSTALL"}
        ]
    }
    
    response = requests.post(
        f"{server_url}/ImplementationGuide/$install",
        data=json.dumps(params),
        headers={
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json"
        }
    )

    if response.status_code not in [200, 201]:
        print(f"Failed to install {package_name}:{version}: {response.status_code} - {response.text}")
        failed.update({f"{package_name}:{version}": response.json()})
        return False

    # HAPI can return 200 with an OperationOutcome containing fatal/error issues
    body = response.json()
    if body.get("resourceType") == "OperationOutcome":
        errors = [
            i for i in body.get("issue", [])
            if i.get("severity") in ("fatal", "error")
        ]
        if errors:
            print(f"Failed to install {package_name}:{version}: OperationOutcome errors:")
            for e in errors:
                print(f"  [{e.get('severity')}] {e.get('diagnostics')}")
            failed.update({f"{package_name}:{version}": body})
            return False

    print(f"Installed {package_name}:{version}")
    return True



def main():
    yaml = YAML()
    yaml.preserve_quotes = True  # also preserve any quoted strings
    
    failed = {}
    num_packages = 0

    #install_packages_from_json(f"{package_path}/package.json",failed)

    add_packages_to_application_yaml(package_path)
    add_private_packages_to_application_yaml(f"{package_path}/private.package.yaml")
  

        
            
            
        
    
    if failed:
        print(f"\nFailed to install {len(failed)} packages:")
        dump_json("operation_outcomes.json", failed)
        return 1

    print(f"\nSuccessfully installed packages")
    return 0

if __name__ == "__main__":
    print("CWD:", os.getcwd())
    print("Files:", os.listdir("."))
    sys.exit(main())

