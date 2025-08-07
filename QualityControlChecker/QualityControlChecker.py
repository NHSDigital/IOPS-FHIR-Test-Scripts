'''A Quality Control Checker for the IOPS FHIR repos, which runs whenever there is a push to any branch. 

This checks the following:
- XML code for errors
- Files are in the correct path
- Certain elements are present and have correct vales as per the UK Core requirments
- Draft / Active Profiles are within the CapabilityStatement

If any of these are deemed incorrect the workflow will fail. '''

import xml.etree.ElementTree as ET
import json
import os
import sys
import re

def getRepoVariables():
    '''Returns the repo name in lower case'''
    repoPath = os.getcwd()
    repoParent = os.path.dirname(repoPath)
    repoName = os.path.basename(repoParent).lower()
    
    '''Creates main variables for use with UKCore and NHSE assets'''
    if 'ukcore' in repoName.lower():
        from repoVariables import ukcoreVar as mainVar
    else:
        from repoVariables import nhseVar as mainVar
    return mainVar,repoName


def openXMLFile(path,file,warnings):        
    try:
        tree = ET.parse("./"+path+"/"+file)
    except Exception as e:
        warnings.append("\t\tThe code has an error that needs to be fixed before it can be checked: "+str(e))
        return {}, warnings
    root = tree.getroot()
    return root,warnings

def checkRetiredStatusXML(root, warnings):
    '''Will return empty for any retired assets'''
    try:
        if root.findall('.//{*}'+str('status'))[0].get('value') == 'retired' and path != 'examples':
            return {}, warnings
    except:
        warnings.append("\t\tstatus - This element is missing")        
    return root,warnings


def openJSONFile(path, file, warnings):
    ''' loads JSON File returns dict named contents '''
    try:
        with open(f"./{path}/{file}", 'r') as j:
            jsonFile = json.loads(j.read())
    except Exception as e:
        print("\t\tThe code has an error that needs to be fixed before it can be checked:"+ str(e))       
        return {}, warnings
    return jsonFile, warnings

def checkRetiredStatusJSON(jsonFile, warnings):
    '''Will return empty for any retired assets'''
    try:    
        if jsonFile['status']=='retired' and path!= 'examples':
            return {}, warnings
    except:
        warnings.append("\t\tstatus - This element is missing")   
    return jsonFile,warnings


def getXMLCoreElements(path,file,warnings):
    '''check for missing elements, returns a list of key elements if present'''
    elements = {}
    fileKeys = ['id','url','name','title','version','date','description','copyright']
    for k in fileKeys:
        try:
            elements.update({k:root.findall('.//{*}'+str(k))[0].get('value')}) 
        except:
            warnings.append("\t\t"+k+" - This element is missing")
    return elements,warnings
        

def getJSONCoreElements(jsonFile,warnings):
    '''check for missing elements, returns a list of key elements if present'''
    fileKeys = ['id','url','name','title','version','date','description','copyright']
    elements = {}
        
    for k in fileKeys:
        try:
            elements.update({k:jsonFile[k]})
        except:
            warnings.append("\t\t"+k+" - This element is missing")
    return elements,warnings


def checkElementNamingConvention(mainVar, elements, warnings, file, path):
    '''checks the elements id, url prefix (base), url suffix (asset name), name, and title are correct, compared to the FileName. If any are missing from elements dict then passes as the issue will be picked up elsewhere.'''
    fileName = os.path.splitext(os.path.basename(file))[0]
    assetPrefix = {'structuredefinitions':'StructureDefinition', 'valuesets': 'ValueSet', 'codesystems': 'CodeSystem'}
    elementsCheck = {}
    if (path == 'codesystems' or path == 'valuesets'):
        fileName = '-'.join(fileName.split('-')[1:])
    elementsCheck['id'] = fileName

    if 'url' in elements:
        elements['url prefix'] = '/'.join(elements['url'].split('/')[:-1])
        if '/'.join(elements['url prefix'].split('/')[:-1]) not in mainVar['ignoreURLPrefix']:
            elementsCheck['url prefix'] = mainVar['urlPrefix']+"/"+assetPrefix[path]
            elements['url suffix'] = elements['url'].split('/')[-1]
            elementsCheck['url suffix'] = fileName 
         
    elementsCheck['name'] = ''.join(fileName.split('-'))    
    elementsCheck['title'] = re.sub(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', ' '.join(fileName.split('-')))
   
    for key,value in elementsCheck.items():
        try:
            if value != elements[key]:
                warnings.append("\t\t"+key+" - The element is incorrect, it should be '"+value+"'")
        except:
            pass
    return warnings
    

def checkXMLStructureDefinitionElements(root,path,warnings):
    ''' Check purpose element is present in Profiles and Extensions '''
    try:
        root.findall('.//{*}'+str('purpose'))[0].get('value')
    except:
        warnings.append("\t\tpurpose - This element is missing'")
    return warnings


def checkJSONStructureDefinitionElements(jsonFile, warnings):
    try:
        jsonFile['purpose']
    except:
        warnings.append("\t\tpurpose - This element is missing'")
    return warnings


def checkContactDetailsXML(root,path,warnings):            
    ''' Check Contact Details '''
    try:
        if not root.findall('.//{*}'+str('name'))[1].get('value') == mainVar['org']:
            warnings.append("\t\tcontact.name - This SHALL be '"+mainVar['org']+"'")
    except:
        print("\t\tcontact.name - This element is missing")
    if 'value' in mainVar:
        contact = {'system':'email','value':mainVar['email'],'use':'work','rank':'1'}
    else:
        contact = {'system':'email','use':'work','rank':'1'}
        
    for key,value in contact.items():
        try:
            if not root.findall('.//{*}'+str(key))[0].get('value') == value:
                try: 
                    if not root.findall('.//{*}'+str(key))[1].get('value') == value: #added as a workaround in case identifier.system and identifier.value present  
                        warnings.append("\t\t"+"contact.telecom."+key+" - This SHALL be '"+value+"'")
                except:
                    warnings.append("\t\t"+"contact.telecom."+key+" - This SHALL be '"+value+"'")
        except:
            warnings.append("\t\tcontact.telecom."+key+" - This element is missing")
    return warnings


def checkContactDetailsJSON(jsonFile,warnings):
    try:
        if not jsonFile['contact'][0]['name'] == mainVar['org']:
            warnings.append("\t\tcontact.name - This SHALL be '"+mainVar['org']+"'")
    except:
        warnings.append("\t\tcontact.name - This SHALL be '"+mainVar['org']+"'")
        
    if 'value' in mainVar:
        contact = {'system':'email','value':mainVar['email'],'use':'work','rank':1}
    else:
        contact = {'system':'email','use':'work','rank':1}
        
    for key,value in contact.items():
        try:
            if not jsonFile['contact'][0]['telecom'][0][key] == value:
                warnings.append("\t\tcontact.telecom."+key+" - This SHALL be '"+value+"'")
        except:
            warnings.append("\t\tcontact.telecom."+key+" - This element is missing")
    return warnings


def checkAssets(file, warnings):
    '''Check files are in correct folder '''
    fileName = os.path.splitext(os.path.basename(file))[0]
    if path == 'structuredefinitions':
        if fileName.endswith("Example") or (not file.startswith('Extension') and not file.startswith(mainVar['project'])):
            warnings.append("\t\tThe file has either an incorrect prefix or in the wrong folder '"+path+"'")
            error=True
        if fileName.startswith(mainVar['project']): #Used for Capabilitystatement Checking
            profile = fileName.replace(mainVar['project']+'-','')
            if '-' not in profile: #ignore derived profiles
                currentProfiles.append(profile)
        if file.endswith("xml"):
            warnings = checkXMLStructureDefinitionElements(root,path,warnings)
        else:
            warnings = checkJSONStructureDefinitionElements(jsonFile,warnings)
    if path == 'valuesets' and not file.startswith('ValueSet'):
        warnings.append("\t\tThe file has either an incorrect prefix or in the wrong folder '"+path+"'")
        error=True
    if path == 'codesystems' and not file.startswith('CodeSystem'):
        warnings.append("\t\tThe file has either an incorrect prefix or in the wrong folder '"+path+"'")
        error=True
    return warnings


def checkExamples(exampleWarnings, example):
    fileName = os.path.splitext(example)[0]
    if not fileName.endswith("-Example") :
        exampleWarnings.append("\t\tThe filename is does not have the suffix '-Example'")
    
    '''open file to find element values'''
    if example.endswith("xml"):
        root, exampleWarnings = openXMLFile("examples",example, exampleWarnings)
        if root != {}:
            try:
                if not root.findall('.//{*}id')[0].get('value') == fileName:
                    exampleWarnings.append("\t\tid - The element is incorrect, it shoud be "+fileName)
            except:
                exampleWarnings.append("\t\tid - This element is missing")
    elif example.endswith("json"):
        elements, exampleWarnngs = openJSONFile("examples",example, exampleWarnings)
        if elements != {}:
            try:
                if not elements['id'] == fileName:
                    exampleWarnings.append("\t\tid - The element is incorrect, it should be "+fileName)
            except:
                exampleWarnings.append("\t\tid - This element is missing")        
    else:
        exampleWarnings.append("\t\tThe file extension SHALL be .xml or .json")
    return exampleWarnings
        
            
def CheckCapabilityStatementProfiles(error,repoName):
    '''CapabilityStatement Checker - checks if all Profiles are in the CapabilityStatement'''
    root = openXMLFile("CapabilityStatements","CapabilityStatement-"+mainVar['project']+".xml")
    print('CapabilityStatement')
    capabilityStatement = []
    if root != None:
        for tag in root.findall('.//{*}type'):
            capabilityStatement.append(tag.attrib["value"])

        for p in currentProfiles:
            if p not in capabilityStatement:
                print("\t",root,"\n",p,"is missing from the CapabilityStatement")
                error=True
    return error

def printWarnings(warnings, file, error):
    if warnings:
        error=True
        print("\t",file)
        for x in warnings:
            print(x)
    return error


print("\n\033[1mNote:The elements id, name, title, url are checked against the filename. If the filename is incorrect expect all these elements to error.\033[0m\n")
'''Creates an error state, if any of the checks fails it will cause the action to fail'''
error=False
mainVar,repoName = getRepoVariables()
currentProfiles = [] #Used for checking against CapabilityStatement

paths = ['structuredefinitions','valuesets','codesystems']

''' Find each file within paths and check for Quality Control. Prints outcome if issues found and sets error to True.'''
for path in paths:
    try:
        files = os.listdir('./'+path)
        print("\n\033[1m"+path.title()+"\033[0m")
    except:
        continue
    for file in files:
        warnings = []
        if 'ext-' in file: # ignore any file brought in via hl7.fhir.uv.xver-.. packages. This is temp until the package is added to the fhir registry
            continue
        if file.endswith("xml"):
            root,warnings = openXMLFile(path,file,warnings)
            root,warnings = checkRetiredStatusXML(root, warnings)
            if root == {}:
                error = printWarnings(warnings, file, error)
                continue
            warnings = checkContactDetailsXML(root, path, warnings)
            elements,warnings = getXMLCoreElements(path, file, warnings)
        elif file.endswith("json"):
            jsonFile,warnings = openJSONFile(path,file,warnings)
            jsonFile,warnings = checkRetiredStatusJSON(jsonFile, warnings)
            if not jsonFile:
                error = printWarnings(warnings, file, error)
                continue
            warnings = checkContactDetailsJSON(jsonFile, warnings)
            elements,warnings = getJSONCoreElements(jsonFile, warnings)
        else:
            print('\t',file,'is neither in xml or json format and has not been checked')
            continue

        warnings = checkAssets(file, warnings)
        warnings = checkElementNamingConvention(mainVar, elements, warnings, file, path)    
        error = printWarnings(warnings, file, error)

''' Check Examples. Prints outcome if issues found and sets error to True.'''
try:
    examplesPath = os.listdir('./examples')
    print("\n\033[1mExamples\033[0m")
except:
    examplesPath = []
for example in examplesPath:
    exampleWarnings = []
    exampleWarnings = checkExamples(exampleWarnings, example)
    error = printWarnings(exampleWarnings, example, error)

''' Checks Capability for missing profiles for UK Core or NHSE IG only '''
if repoName == 'FHIR-R4-UKCORE-STAGING-MAIN' or repoName == 'NHSEngland-FHIR-ImplementationGuide':
    CheckCapabilityStatementProfiles(error,repoName)

''' If any QC issues found within the script, cause the action to fail''' 
if error == True:
    print("\n\033[1mPlease fix the errors found above before merging\033[0m")
    sys.exit(2)
else:
    print("\n\n\033[1mCheck Complete!\033[0m")
