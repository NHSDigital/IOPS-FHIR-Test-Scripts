import {
    getFhirClientJSON, NEW_LINE, testFileError, testFileErrorProfile, testFileValidator, testFileWarning,
} from "./common.js";
import {describe, expect, jest} from "@jest/globals";
import {AxiosInstance} from "axios";
import fs from "fs";



const args = require('minimist')(process.argv.slice(2))


let terminology = true;
jest.setTimeout(120_000)

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

    // TODO This should be a pass
    testFileError('Test EPS fhirPath constraint issue (present in 6.2.x HAPI) ','Examples/pass/MedicationRequest-constraints.json', undefined)
});

describe('Testing validation fails invalid FHIR resources', () => {

    //Patient
    

    // PractitionerRole


    // MedicationRequest
    testFileError('Check validation fails when no medication code is supplied', 'Examples/fail/MedicationRequest-missingMedication.json',undefined)
  //  testFileError('Check validation fails when no medication code is supplied','Examples/fail/MedicationRequest-missingMedication.json','MedicationRequest.medication[x]: minimum required = 1')
    testFileError('Check validation fails when identifier is an object not an array (AEA-1820)','Examples/fail/MedicationRequest-invalid-json.json', undefined)

    // MedicationDispense
    testFileError('Check validation fails when daysSupply has an incorrect unitsofmeasure code','Examples/fail/MedicationDispense-daysSupply-invalidaUnitOfMeasure.json',undefined)
    testFileError('Check validation fails when dosageInstruction.timing has an incorrect unitsofmeasure code','Examples/fail/MedicationDispense-timing-invalidaUnitOfMeasure.json','UnitsOfTime')

    testFileError('Check validation fails when MedicationRequest references Patient in the MessageHeader.focus but is present','Examples/fail/Bundle-prescription-order-incorrectFocus.json', 'Invalid Resource target type.')
    // Should be in MessageDefinition??
    testFileWarning('Check validation fails when Location is referenced but not present in the FHIR Message','Examples/fail/Bundle-prescription-order-locationNotPresent.json', 'URN reference is not locally contained within the bundle')

    testFileError('Check validation fails when Message Bundle.entry.fullUrl is absent','Examples/fail/Bundle-prescription-order-missingFullUrl.json','Bundle entry missing fullUrl')
    testFileError('Check validation fails when SearchSet Bundle.entry.fullUrl is absent (AEA-1828)','Examples/fail/Bundle-searchset-COVIDExemption-missingFullUrl.json','Except for transactions and batches')

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



