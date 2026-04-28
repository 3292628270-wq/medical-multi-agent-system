/** Agent 输出数据结构 */

export interface AgentEvent {
  agent: string | null
  output: Record<string, unknown> | null
  complete: boolean
}

export interface PatientInfo {
  name: string
  age: number
  gender: string
  chief_complaint: string
  symptoms: Array<{
    name: string
    duration_days?: number
    severity: string
    description?: string
  }>
  medical_history: string[]
  family_history: string[]
  allergies: Array<{ substance: string; reaction?: string; severity: string }>
  current_medications: Array<{ name: string; dosage?: string; frequency?: string }>
  vital_signs: Record<string, number | null> | null
  lab_results: Array<{ test_name: string; value: string; unit?: string; is_abnormal: boolean }>
}

export interface DiagnosisData {
  primary_diagnosis: {
    disease_name: string
    icd10_hint: string
    confidence: number
    evidence: string[]
    reasoning: string
  }
  differential_list: Array<{
    disease_name: string
    icd10_hint: string
    confidence: number
    evidence: string[]
    reasoning: string
  }>
  recommended_tests: string[]
  clinical_notes: string
  knowledge_sources: string[]
}

export interface TreatmentData {
  diagnosis_addressed: string
  medications: Array<{
    drug_name: string
    generic_name: string
    dosage: string
    route: string
    frequency: string
    duration: string
    contraindications: string[]
    side_effects: string[]
  }>
  drug_interactions: Array<{
    drug_a: string
    drug_b: string
    severity: string
    description: string
    recommendation: string
  }>
  non_drug_treatments: string[]
  lifestyle_recommendations: string[]
  follow_up_plan: string
  warnings: string[]
  evidence_references: string[]
}

export interface CodingData {
  primary_icd10: {
    code: string
    description: string
    confidence: number
    category: string
  }
  secondary_icd10_codes: Array<{
    code: string
    description: string
    confidence: number
    category: string
  }>
  drg_group: {
    drg_code: string
    description: string
    weight: number
    mean_los: number
  } | null
  coding_notes: string
  coding_confidence: number
}

export interface AuditData {
  hipaa_compliant: boolean
  compliance_checks: Array<{
    check_name: string
    passed: boolean
    detail: string
  }>
  phi_fields_found: string[]
  phi_fields_masked: string[]
  audit_trail: Array<{
    timestamp: string
    action: string
    detail: string
  }>
  recommendations: string[]
  overall_risk_level: string
}

export type AgentName = 'intake' | 'diagnosis' | 'treatment' | 'coding' | 'audit'

export interface AgentStatus {
  name: AgentName
  label: string
  status: 'pending' | 'running' | 'done'
  output?: Record<string, unknown>
}
