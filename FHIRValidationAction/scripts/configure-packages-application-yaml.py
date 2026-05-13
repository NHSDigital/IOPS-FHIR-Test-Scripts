#!/usr/bin/env python3
"""Install FHIR package dependencies from package.json"""

import json
import sys
import os
from common import dump_json
from pathlib import Path
from ruamel.yaml import YAML


script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "config.json")

#for github actions
test_script_repo_path = f"./validation/FHIRValidationAction"
package_path = "."
application_yaml = "./validation-service-fhir-r4/hapi.application.yaml"


#for testing locally
#test_script_repo_path = "./FHIRValidationAction" 
#package_path = "../NHSEngland-FHIR-Programme-Pathology" #"./FHIRValidationAction/test"
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
        
        if 'implementationguides' not in data['hapi']['fhir']:
            data['hapi']['fhir']['implementationguides'] = {}
        
        data['hapi']['fhir']['implementationguides'][package_key] = package_entry

    with open(application_yaml, "w") as f:
        yaml.dump(data, f)
    return len(package_dependencies)

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
    return len(source_guides)

def get_package_dependencies(package_path):
    try:       
        with open(f"{package_path}/package.json") as f:
            package = json.load(f)
            package_dependencies = package.get('dependencies', {})
            return package_dependencies
    except FileNotFoundError:
        print("No package.json found - skipping package installation")
        return 0



def main():
    yaml = YAML()
    yaml.preserve_quotes = True  # also preserve any quoted strings
    
    num_packages = add_packages_to_application_yaml(package_path)
    num_private_packages = add_private_packages_to_application_yaml(f"{package_path}/private.package.yaml")
  
    print(f"\nAdded {num_packages+num_private_packages} packages for installation")
    return 0

if __name__ == "__main__":
    print("CWD:", os.getcwd())
    print("Files:", os.listdir("."))
    sys.exit(main())

