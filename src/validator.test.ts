import {
    getFhirClientJSON, NEW_LINE, testFileError, testFileErrorProfile, testFileValidator, testFileWarning,
} from "./common.js";
import {describe, expect, jest} from "@jest/globals";
import {AxiosInstance} from "axios";
import fs from "fs";



const args = require('minimist')(process.argv.slice(2))


let terminology = true;
jest.setTimeout(40*1000)

let gitHubSummary = '### :fire_engine: Logs '+NEW_LINE;

    let failOnWarning = true;
    if (process.env.FAILONWARNING != undefined && process.env.FAILONWARNING.toLowerCase() == 'false') {
        failOnWarning = false;
    }
    gitHubSummary += 'Strict validation: ' + failOnWarning + NEW_LINE;

describe('Test Environment', ()=> {
    let client: AxiosInstance;
    beforeAll(async () => {
        client = await getFhirClientJSON();
    });
    test('Validator is functioning ', async function () {

        const result = await client.get('/metadata')
        expect(result.status).toEqual(200)

    })
});

describe('Testing validation passes for valid HL7 FHIR resources', () => {
    // Patient
    testFileValidator('Test HL7 FHIR resource passes validation ','Examples/pass/patient.json')

    // MedicationRequest
    testFileValidator('Test HL7 FHIR resource passes validation ','Examples/pass/MedicationRequest-pass.json')

    // MedicationDispense
    testFileValidator('Test HL7 FHIR resource passes validation ','Examples/pass/MedicationDispense-pass.json')

    // Bundle
    testFileValidator('Test HL7 FHIR Seaarch Immmunization Bundle passes validation ','Examples/pass/Bundle-searchset-COVIDImmunization.json')
    testFileValidator('Test HL7 FHIR Seaarch Observation Bundle passes validation ','Examples/pass/Bundle-searchset-COVIDObservation.json')
    testFileValidator('Test resource with unknown profile passes validation (AEA-1806) ','Examples/pass/MedicationRequest-alienProfile-pass.json')
    testFileValidator('Test prescription-order-response is tested with correct NHSDigital-MedicationRequest-Outcome profile and not NHSDigital-MedicationRequest (AEA-1805) ','Examples/pass/outpatient-four-items-cancel-subsequent-response-morphine.json')

    // TODO This should be a pass
    testFileError('Test EPS fhirPath constraint issue (present in 6.2.x HAPI) ','Examples/pass/MedicationRequest-constraints.json', undefined)
});

describe('Testing validation fails invalid FHIR resources', () => {

    //Patient
    testFileErrorProfile('Check validation fails when no NHS Number is supplied','Examples/fail/patientError.json','Patient.identifier:nhsNumber: minimum required = 1','https://fhir.nhs.uk/StructureDefinition/NHSDigital-Patient-PDS')
    testFileError('Check validation fails when no Scottish CHI Number is supplied','Examples/fail/patient-chi-number.json','Supplied NHS Number is outside the English and Welsh NHS Number')

    // PractitionerRole
    testFileError('Check validation fails on PractitionerRole when invalid GMC Number is supplied','Examples/fail/PractitionerRole-invalidGMC.json','GMC must be of the format CNNNNNNN')


    // MedicationRequest
    testFileError('Check validation fails when no medication code is supplied', 'Examples/fail/MedicationRequest-missingMedication.json',undefined)
  //  testFileError('Check validation fails when no medication code is supplied','Examples/fail/MedicationRequest-missingMedication.json','MedicationRequest.medication[x]: minimum required = 1')
    testFileError('Check validation fails when medication code is supplied with the future dm+d system', 'Examples/fail/MedicationRequest-dmdCode.json','CodeableConcept.coding:SNOMED')
    testFileError('Check validation fails when identifier is an object not an array (AEA-1820)','Examples/fail/MedicationRequest-invalid-json.json', undefined)

    // MedicationDispense
    testFileError('Check validation fails when daysSupply has an incorrect unitsofmeasure code','Examples/fail/MedicationDispense-daysSupply-invalidaUnitOfMeasure.json',undefined)
    testFileError('Check validation fails when dosageInstruction.timing has an incorrect unitsofmeasure code','Examples/fail/MedicationDispense-timing-invalidaUnitOfMeasure.json','UnitsOfTime')
    testFileError('Check validation fails when medication code is supplied with the future dm+d system','Examples/fail/MedicationDispense-dmdCode.json','CodeableConcept.coding:SNOMED: minimum required = 1')

    testFileError('Check validation fails when MedicationRequest references Patient in the MessageHeader.focus but is present','Examples/fail/Bundle-prescription-order-incorrectFocus.json', 'Invalid Resource target type.')
    // Should be in MessageDefinition??
    testFileWarning('Check validation fails when Location is referenced but not present in the FHIR Message','Examples/fail/Bundle-prescription-order-locationNotPresent.json', 'URN reference is not locally contained within the bundle')

    testFileError('Check validation fails when Message Bundle.entry.fullUrl is absent','Examples/fail/Bundle-prescription-order-missingFullUrl.json','Bundle entry missing fullUrl')
    testFileError('Check validation fails when SearchSet Bundle.entry.fullUrl is absent (AEA-1828)','Examples/fail/Bundle-searchset-COVIDExemption-missingFullUrl.json','Except for transactions and batches')

    testFileError('Test HL7 FHIR Message Bundle passes validation (AEA-1833)','Examples/fail/Bundle-prescription-rest-references.json','Bundled or contained reference not found within the bundle')
});



describe('Terminology Tests', () => {
    if (terminology) {
        testFileError('Check validation fails when non dm+d SNOMED drug code is supplied', 'Examples/fail/MedicationRequest-not-dmd-drug.json', 'is not in the value set')
    }
});

const gitSummaryFile = process.env.GITHUB_STEP_SUMMARY
console.info('GitSummary Text = '+gitHubSummary)
if (fs.existsSync(gitSummaryFile)) {
    console.info('Git Summary found :' + gitSummaryFile)
    try {
        fs.appendFileSync(gitSummaryFile, gitHubSummary);
    } catch (e) {
        console.info('Error processing '+ gitSummaryFile + ' Error message '+ (e as Error).message)
    }
} else {
    console.info('Git Summary not found :' + gitSummaryFile)
}



