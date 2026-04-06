"""
GraphRAG service — Medical knowledge graph retrieval.

Integrates with Neo4j to provide:
  - Symptom-to-disease relationship queries
  - Disease-to-treatment pathway lookups
  - Multi-hop reasoning across medical ontologies (UMLS, SNOMED, ICD)
  - Evidence retrieval for clinical decision support
"""

from __future__ import annotations
from typing import Optional
import structlog

from ..config.settings import get_settings

logger = structlog.get_logger(__name__)

# Pre-built knowledge base for demonstration (offline mode)
SYMPTOM_DISEASE_MAP = {
    "fever": ["Influenza", "Pneumonia", "COVID-19", "Sepsis", "Malaria", "UTI"],
    "cough": ["Pneumonia", "Bronchitis", "Asthma", "COPD", "Lung Cancer", "COVID-19"],
    "headache": ["Migraine", "Tension Headache", "Meningitis", "Hypertension", "Brain Tumor"],
    "chest_pain": ["Acute MI", "Angina", "Pulmonary Embolism", "Pneumothorax", "GERD"],
    "abdominal_pain": ["Appendicitis", "Cholecystitis", "Pancreatitis", "Peptic Ulcer", "IBS"],
    "shortness_of_breath": ["Asthma", "COPD", "Heart Failure", "Pneumonia", "Pulmonary Embolism"],
    "fatigue": ["Anemia", "Hypothyroidism", "Depression", "Diabetes", "Heart Failure"],
    "nausea": ["Gastroenteritis", "Pregnancy", "Appendicitis", "Migraine", "Hepatitis"],
    "dizziness": ["BPPV", "Hypotension", "Anemia", "Stroke", "Arrhythmia"],
    "joint_pain": ["Rheumatoid Arthritis", "Osteoarthritis", "Gout", "SLE", "Lyme Disease"],
}

DISEASE_ICD10_MAP = {
    "Pneumonia": {"code": "J18.9", "desc": "Pneumonia, unspecified organism"},
    "Influenza": {"code": "J11.1", "desc": "Influenza with other respiratory manifestations"},
    "COVID-19": {"code": "U07.1", "desc": "COVID-19, virus identified"},
    "Acute MI": {"code": "I21.9", "desc": "Acute myocardial infarction, unspecified"},
    "Asthma": {"code": "J45.909", "desc": "Unspecified asthma, uncomplicated"},
    "Type 2 Diabetes": {"code": "E11.9", "desc": "Type 2 diabetes mellitus without complications"},
    "Hypertension": {"code": "I10", "desc": "Essential (primary) hypertension"},
    "Heart Failure": {"code": "I50.9", "desc": "Heart failure, unspecified"},
    "COPD": {"code": "J44.1", "desc": "COPD with acute exacerbation"},
    "Appendicitis": {"code": "K35.80", "desc": "Unspecified acute appendicitis"},
    "Migraine": {"code": "G43.909", "desc": "Migraine, unspecified, not intractable"},
    "Anemia": {"code": "D64.9", "desc": "Anemia, unspecified"},
    "UTI": {"code": "N39.0", "desc": "Urinary tract infection, site not specified"},
    "Depression": {"code": "F32.9", "desc": "Major depressive disorder, single episode, unspecified"},
    "Sepsis": {"code": "A41.9", "desc": "Sepsis, unspecified organism"},
}


class GraphRAGService:
    """
    Medical knowledge graph retrieval service.

    In production, this connects to Neo4j and performs Cypher queries.
    For demo/testing, uses the built-in knowledge maps above.
    """

    def __init__(self, use_neo4j: bool = False):
        self.use_neo4j = use_neo4j
        self._driver = None

    async def connect(self):
        if self.use_neo4j:
            try:
                from neo4j import AsyncGraphDatabase
                settings = get_settings()
                self._driver = AsyncGraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
                logger.info("graphrag.neo4j_connected")
            except Exception as e:
                logger.warning("graphrag.neo4j_fallback", error=str(e))
                self.use_neo4j = False

    def find_diseases_by_symptoms(self, symptoms: list[str]) -> list[dict]:
        """Find candidate diseases given a list of symptom names."""
        disease_scores: dict[str, int] = {}
        for symptom in symptoms:
            key = symptom.lower().replace(" ", "_")
            for disease in SYMPTOM_DISEASE_MAP.get(key, []):
                disease_scores[disease] = disease_scores.get(disease, 0) + 1

        ranked = sorted(disease_scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for disease, score in ranked:
            icd = DISEASE_ICD10_MAP.get(disease, {})
            results.append({
                "disease": disease,
                "symptom_match_count": score,
                "icd10_code": icd.get("code", ""),
                "icd10_description": icd.get("desc", ""),
            })
        return results

    def get_icd10(self, disease_name: str) -> Optional[dict]:
        """Look up ICD-10 code for a disease name."""
        return DISEASE_ICD10_MAP.get(disease_name)

    async def query_neo4j(self, cypher: str, params: dict = None) -> list[dict]:
        """Execute a Cypher query against Neo4j (production mode)."""
        if not self._driver:
            logger.warning("graphrag.neo4j_not_connected")
            return []
        async with self._driver.session() as session:
            result = await session.run(cypher, params or {})
            return [record.data() async for record in result]

    async def close(self):
        if self._driver:
            await self._driver.close()


_service: Optional[GraphRAGService] = None


def get_graphrag_service() -> GraphRAGService:
    global _service
    if _service is None:
        _service = GraphRAGService(use_neo4j=False)
    return _service
