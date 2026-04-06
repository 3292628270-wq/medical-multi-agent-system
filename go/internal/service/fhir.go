package service

import (
	"fmt"
	"time"
)

// PatientToFHIR converts an internal patient_info map to a FHIR R4 Patient resource.
func PatientToFHIR(patientInfo map[string]interface{}) map[string]interface{} {
	gender := "unknown"
	if g, ok := patientInfo["gender"].(string); ok {
		switch g {
		case "male", "female", "other":
			gender = g
		}
	}

	birthYear := time.Now().Year()
	if age, ok := patientInfo["age"].(float64); ok && age > 0 {
		birthYear -= int(age)
	}

	resource := map[string]interface{}{
		"resourceType": "Patient",
		"id":           patientInfo["patient_id"],
		"name": []map[string]interface{}{
			{
				"use":  "official",
				"text": mapGetString(patientInfo, "name", "Unknown"),
			},
		},
		"gender":    gender,
		"birthDate": fmt.Sprintf("%d-01-01", birthYear),
	}

	if allergies, ok := patientInfo["allergies"].([]interface{}); ok && len(allergies) > 0 {
		var allergyResources []map[string]interface{}
		for _, a := range allergies {
			if am, ok := a.(map[string]interface{}); ok {
				allergyResources = append(allergyResources, map[string]interface{}{
					"resourceType": "AllergyIntolerance",
					"substance":    am["substance"],
					"reaction":     am["reaction"],
				})
			}
		}
		resource["_allergies"] = allergyResources
	}

	return resource
}

// DiagnosisToFHIRCondition converts a diagnosis map to a FHIR R4 Condition resource.
func DiagnosisToFHIRCondition(diagnosis map[string]interface{}, patientID string) map[string]interface{} {
	primary, _ := diagnosis["primary_diagnosis"].(map[string]interface{})
	if primary == nil {
		primary = map[string]interface{}{}
	}

	return map[string]interface{}{
		"resourceType": "Condition",
		"subject":      map[string]interface{}{"reference": "Patient/" + patientID},
		"code": map[string]interface{}{
			"coding": []map[string]interface{}{
				{
					"system":  "http://hl7.org/fhir/sid/icd-10-cm",
					"code":    primary["icd10_hint"],
					"display": primary["disease_name"],
				},
			},
			"text": primary["disease_name"],
		},
		"note": []map[string]interface{}{
			{"text": primary["reasoning"]},
		},
	}
}

// MedicationToFHIR converts a prescribed medication to a FHIR R4 MedicationRequest.
func MedicationToFHIR(medication map[string]interface{}, patientID string) map[string]interface{} {
	genericName := mapGetString(medication, "generic_name", mapGetString(medication, "drug_name", ""))

	return map[string]interface{}{
		"resourceType": "MedicationRequest",
		"status":       "active",
		"intent":       "order",
		"subject":      map[string]interface{}{"reference": "Patient/" + patientID},
		"medicationCodeableConcept": map[string]interface{}{
			"text": medication["drug_name"],
			"coding": []map[string]interface{}{
				{"display": genericName},
			},
		},
		"dosageInstruction": []map[string]interface{}{
			{
				"text": fmt.Sprintf("%v %v %v",
					medication["dosage"],
					mapGetString(medication, "route", "oral"),
					medication["frequency"],
				),
				"timing": map[string]interface{}{"code": map[string]interface{}{"text": medication["frequency"]}},
				"route":  map[string]interface{}{"text": mapGetString(medication, "route", "oral")},
				"doseAndRate": []map[string]interface{}{
					{"doseQuantity": map[string]interface{}{"value": medication["dosage"]}},
				},
			},
		},
	}
}

func mapGetString(m map[string]interface{}, key, fallback string) string {
	if v, ok := m[key].(string); ok && v != "" {
		return v
	}
	return fallback
}
