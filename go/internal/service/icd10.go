package service

import "strings"

// ICD10Entry represents a single ICD-10-CM code with its description and category.
type ICD10Entry struct {
	Code        string `json:"code"`
	Description string `json:"description"`
	Category    string `json:"category"`
}

// DRGGroup represents a DRGs grouping result.
type DRGGroup struct {
	DRGCode     string  `json:"drg_code"`
	Description string  `json:"description"`
	Weight      float64 `json:"weight"`
	MeanLOS     float64 `json:"mean_los"`
}

type icd10Category struct {
	Name  string
	Codes map[string]string
}

var icd10Database = []icd10Category{
	{
		Name: "Certain infectious and parasitic diseases",
		Codes: map[string]string{
			"A41.9": "Sepsis, unspecified organism",
			"A49.9": "Bacterial infection, unspecified",
			"B34.9": "Viral infection, unspecified",
		},
	},
	{
		Name: "Neoplasms",
		Codes: map[string]string{
			"C34.90":  "Malignant neoplasm of unspecified part of bronchus or lung",
			"C50.919": "Malignant neoplasm of unspecified site of breast",
		},
	},
	{
		Name: "Blood diseases",
		Codes: map[string]string{
			"D64.9": "Anemia, unspecified",
			"D69.6": "Thrombocytopenia, unspecified",
		},
	},
	{
		Name: "Endocrine, nutritional and metabolic diseases",
		Codes: map[string]string{
			"E11.9":  "Type 2 diabetes mellitus without complications",
			"E11.65": "Type 2 diabetes mellitus with hyperglycemia",
			"E03.9":  "Hypothyroidism, unspecified",
			"E78.5":  "Hyperlipidemia, unspecified",
		},
	},
	{
		Name: "Mental and behavioral disorders",
		Codes: map[string]string{
			"F32.9": "Major depressive disorder, single episode, unspecified",
			"F41.1": "Generalized anxiety disorder",
		},
	},
	{
		Name: "Nervous system diseases",
		Codes: map[string]string{
			"G43.909": "Migraine, unspecified, not intractable",
			"G47.00":  "Insomnia, unspecified",
		},
	},
	{
		Name: "Circulatory system diseases",
		Codes: map[string]string{
			"I10":    "Essential (primary) hypertension",
			"I21.9":  "Acute myocardial infarction, unspecified",
			"I50.9":  "Heart failure, unspecified",
			"I63.9":  "Cerebral infarction, unspecified",
			"I25.10": "Atherosclerotic heart disease of native coronary artery",
		},
	},
	{
		Name: "Respiratory system diseases",
		Codes: map[string]string{
			"J06.9":   "Acute upper respiratory infection, unspecified",
			"J11.1":   "Influenza with other respiratory manifestations",
			"J18.1":   "Lobar pneumonia, unspecified organism",
			"J18.9":   "Pneumonia, unspecified organism",
			"J44.1":   "COPD with acute exacerbation",
			"J45.909": "Unspecified asthma, uncomplicated",
		},
	},
	{
		Name: "Digestive system diseases",
		Codes: map[string]string{
			"K21.0":  "GERD with esophagitis",
			"K35.80": "Unspecified acute appendicitis",
			"K80.20": "Calculus of gallbladder without cholecystitis",
		},
	},
	{
		Name: "Genitourinary system diseases",
		Codes: map[string]string{
			"N39.0": "Urinary tract infection, site not specified",
			"N18.9": "Chronic kidney disease, unspecified",
		},
	},
	{
		Name: "Codes for special purposes",
		Codes: map[string]string{
			"U07.1": "COVID-19, virus identified",
		},
	},
}

type drgEntry struct {
	DRG    string
	Desc   string
	Weight float64
	LOS    float64
}

var drgGroups = map[string]drgEntry{
	"J18": {DRG: "193", Desc: "Simple Pneumonia & Pleurisy w MCC", Weight: 1.4, LOS: 4.5},
	"I21": {DRG: "280", Desc: "Acute Myocardial Infarction w MCC", Weight: 2.1, LOS: 5.2},
	"I50": {DRG: "291", Desc: "Heart Failure & Shock w MCC", Weight: 1.6, LOS: 5.0},
	"J44": {DRG: "190", Desc: "COPD w MCC", Weight: 1.3, LOS: 4.0},
	"A41": {DRG: "871", Desc: "Septicemia or Severe Sepsis w MCC", Weight: 2.3, LOS: 6.5},
	"E11": {DRG: "637", Desc: "Diabetes w MCC", Weight: 1.2, LOS: 3.8},
	"K35": {DRG: "343", Desc: "Appendectomy w/o CC/MCC", Weight: 1.5, LOS: 2.5},
	"I63": {DRG: "061", Desc: "Ischemic Stroke w Thrombolytic", Weight: 2.5, LOS: 5.8},
	"N39": {DRG: "690", Desc: "Kidney & UTI w/o MCC", Weight: 0.8, LOS: 3.2},
}

// LookupICD10 looks up a single ICD-10 code in the built-in database.
func LookupICD10(code string) *ICD10Entry {
	for _, cat := range icd10Database {
		if desc, ok := cat.Codes[code]; ok {
			return &ICD10Entry{Code: code, Description: desc, Category: cat.Name}
		}
	}
	return nil
}

// SearchICD10ByText searches ICD-10 codes by keyword in descriptions.
func SearchICD10ByText(text string) []ICD10Entry {
	lower := strings.ToLower(text)
	var results []ICD10Entry
	for _, cat := range icd10Database {
		for code, desc := range cat.Codes {
			if strings.Contains(strings.ToLower(desc), lower) {
				results = append(results, ICD10Entry{Code: code, Description: desc, Category: cat.Name})
			}
		}
	}
	return results
}

// GetDRGGroup returns the DRGs grouping for a given ICD-10 code prefix.
func GetDRGGroup(icd10Code string) *DRGGroup {
	prefix := icd10Code
	if idx := strings.Index(icd10Code, "."); idx >= 0 {
		prefix = icd10Code[:idx]
	} else if len(prefix) > 3 {
		prefix = prefix[:3]
	}
	if entry, ok := drgGroups[prefix]; ok {
		return &DRGGroup{
			DRGCode:     entry.DRG,
			Description: entry.Desc,
			Weight:      entry.Weight,
			MeanLOS:     entry.LOS,
		}
	}
	return nil
}

// ValidateICD10Code checks whether a code exists in the built-in database.
func ValidateICD10Code(code string) bool {
	return LookupICD10(code) != nil
}
