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


script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "config.json")

#for github actions
#test_script_repo_path = f"{Path.cwd()}/validation"
#package_path = Path.cwd()

#for testing locally
test_script_repo_path = "." 
package_path = "./test"

with open(config_path,"r") as f:
    config = json.load(f)
SERVER_URL = config["fhir-validator"]["base_url"]


def check_package_locally(package_id, version):
    name = f"{package_id}-{version}.tgz"
    for _, _, files in os.walk(f"{test_script_repo_path}/packages"):
        print(files)
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
    
def install_package(package_id, version, server_url, failed):
    package_path = f"{test_script_repo_path}/packages/{package_id}-{version}.tgz"
    
    with open(package_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    params = {
        "resourceType": "Parameters",
        "parameter": [
            {
                "name": "npmContent",
                "valueBase64Binary": encoded
            }
        ]
    }
    
    response = requests.post(
        f"{server_url}/ImplementationGuide/$install",
        json=params,
        headers={
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json"}
    )
    if response.status_code in [200, 201]:
        print(f"Installed {package_id}:{version}")
        return True
    else:
        print(f"Failed to install {package_id}:{version}: {response.status_code} - {response.text}")
        failed.update({f"{package_id}:{version}":response.json()})
        #append_failure(f"{package_id}:{version}", response.json(), failed)
        return False



def main():

    failed = {}

    try:       
        with open(f"{package_path}/package.json") as f:
            package = json.load(f)
    except FileNotFoundError:
        print("No package.json found - skipping package installation")
        return 0
    
    dependencies = package.get('dependencies', {})
    num_packages = len(dependencies)
    
    if not dependencies:
        print("No dependencies found in package.json")
        return 0
    
    print(f"Installing FHIR packages...")
    

    for package_id, version in dependencies.items():
        # Give server time between installations
        if package_id == "hl7.fhir.r4.core":
            num_packages -= 1
            continue  # Skip core package since it's already on the server
        time.sleep(2)
        print(f"\tInstalling {package_id}:{version}")
        if not check_package_locally(package_id, version):
            if not download_package(package_id, version, failed):
                continue

        install_package(package_id, version, SERVER_URL, failed)
            
            
        
    
    if failed:
        print(f"\nFailed to install {len(failed)} packages:")
        dump_json("operation_outcomes.json", failed)
        return 1
    
    print(f"\nSuccessfully installed {num_packages} packages")
    return 0

if __name__ == "__main__":
    print("CWD:", os.getcwd())
    print("Files:", os.listdir("."))
    sys.exit(main())

