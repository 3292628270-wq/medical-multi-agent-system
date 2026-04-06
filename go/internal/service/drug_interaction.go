package service

import "strings"

// DrugInteraction describes a known drug-drug interaction.
type DrugInteraction struct {
	DrugA          string `json:"drug_a"`
	DrugB          string `json:"drug_b"`
	Severity       string `json:"severity"`
	Description    string `json:"description"`
	Recommendation string `json:"recommendation"`
}

var ddiDatabase = []DrugInteraction{
	{"warfarin", "aspirin", "major", "Increased risk of bleeding when warfarin is combined with aspirin", "Avoid combination unless specifically indicated; monitor INR closely"},
	{"metformin", "contrast_dye", "major", "Risk of lactic acidosis with iodinated contrast media", "Discontinue metformin 48h before and after contrast procedures"},
	{"ssri", "maoi", "contraindicated", "Serotonin syndrome risk — potentially fatal", "Absolute contraindication; allow 14-day washout period between medications"},
	{"ace_inhibitor", "potassium_supplement", "moderate", "Risk of hyperkalemia", "Monitor serum potassium levels regularly"},
	{"simvastatin", "amiodarone", "major", "Increased risk of rhabdomyolysis", "Limit simvastatin to 20mg/day when combined with amiodarone"},
	{"ciprofloxacin", "antacid", "moderate", "Reduced absorption of ciprofloxacin", "Take ciprofloxacin 2h before or 6h after antacids"},
	{"methotrexate", "nsaid", "major", "NSAIDs can increase methotrexate toxicity by reducing renal clearance", "Avoid combination or closely monitor blood counts and renal function"},
	{"digoxin", "amiodarone", "major", "Amiodarone increases digoxin levels, risk of toxicity", "Reduce digoxin dose by 50% when starting amiodarone"},
	{"lithium", "nsaid", "major", "NSAIDs can increase lithium levels", "Monitor lithium levels closely; consider dose reduction"},
	{"clopidogrel", "omeprazole", "moderate", "Omeprazole may reduce clopidogrel effectiveness via CYP2C19 inhibition", "Use pantoprazole instead if PPI is needed"},
}

var drugClassMap = map[string]string{
	"lisinopril":      "ace_inhibitor",
	"enalapril":       "ace_inhibitor",
	"ramipril":        "ace_inhibitor",
	"fluoxetine":      "ssri",
	"sertraline":      "ssri",
	"paroxetine":      "ssri",
	"escitalopram":    "ssri",
	"ibuprofen":       "nsaid",
	"naproxen":        "nsaid",
	"diclofenac":      "nsaid",
	"celecoxib":       "nsaid",
	"phenelzine":      "maoi",
	"tranylcypromine": "maoi",
}

func normalizeDrug(name string) []string {
	lower := strings.ToLower(strings.TrimSpace(name))
	candidates := []string{lower}
	if class, ok := drugClassMap[lower]; ok {
		candidates = append(candidates, class)
	}
	return candidates
}

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}

// CheckInteractions checks for drug-drug interactions between new prescriptions
// and current medications.
func CheckInteractions(newDrugs, currentDrugs []string) []DrugInteraction {
	var allNew, allCurrent []string
	for _, d := range newDrugs {
		allNew = append(allNew, normalizeDrug(d)...)
	}
	for _, d := range currentDrugs {
		allCurrent = append(allCurrent, normalizeDrug(d)...)
	}

	var interactions []DrugInteraction
	for _, ddi := range ddiDatabase {
		a, b := ddi.DrugA, ddi.DrugB
		matched := (contains(allNew, a) && contains(allCurrent, b)) ||
			(contains(allNew, b) && contains(allCurrent, a)) ||
			(contains(allNew, a) && contains(allNew, b))
		if matched {
			interactions = append(interactions, ddi)
		}
	}
	return interactions
}

// CheckAllergyContraindication checks if a drug conflicts with known allergies.
func CheckAllergyContraindication(drug string, allergies []string) *DrugInteraction {
	drugLower := strings.ToLower(drug)
	for _, allergy := range allergies {
		allergyLower := strings.ToLower(allergy)
		if strings.Contains(allergyLower, drugLower) || strings.Contains(drugLower, allergyLower) {
			return &DrugInteraction{
				DrugA:          drug,
				DrugB:          allergy,
				Severity:       "contraindicated",
				Description:    "Patient has known allergy to " + allergy,
				Recommendation: "Do NOT prescribe " + drug + " — patient has allergy to " + allergy,
			}
		}
		if strings.Contains(allergyLower, "penicillin") && (drugLower == "amoxicillin" || drugLower == "ampicillin") {
			return &DrugInteraction{
				DrugA:          drug,
				DrugB:          allergy,
				Severity:       "major",
				Description:    "Cross-reactivity risk with penicillin allergy (~10%)",
				Recommendation: "Cross-reactivity risk: " + drug + " with penicillin allergy",
			}
		}
	}
	return nil
}
