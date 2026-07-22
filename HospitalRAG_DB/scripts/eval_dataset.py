"""
Module 10 -- the labeled evaluation set. Each case names the document
title(s) a good retriever should surface for that question. Written by
hand against the seeded sample documents in scripts/sample_documents/,
deliberately including a few questions that share little vocabulary
with their source document (e.g. "fever medicine dosage" vs.
"paracetamol") -- those are the cases that show semantic search earning
its complexity over plain keyword search. See docs/03_optimization.md.
"""

EVAL_CASES = [
    {
        "question": "What is the treatment protocol for dengue fever?",
        "expected_document_titles": ["Dengue Fever Treatment Protocol"],
    },
    {
        "question": "Can I give ibuprofen to a dengue patient for fever?",
        "expected_document_titles": ["Dengue Fever Treatment Protocol"],
    },
    {
        "question": "How should hypertension be managed in adult outpatients?",
        "expected_document_titles": ["Hypertension Management Guideline"],
    },
    {
        "question": "What blood pressure reading counts as a hypertensive emergency?",
        "expected_document_titles": ["Hypertension Management Guideline"],
    },
    {
        "question": "What is the maximum daily dose of paracetamol for a healthy adult?",
        "expected_document_titles": ["Paracetamol Dosage Information"],
    },
    {
        "question": "What is the antidote for acetaminophen overdose?",
        "expected_document_titles": ["Paracetamol Dosage Information"],
    },
    {
        "question": "What are the WHO's 5 moments for hand hygiene?",
        "expected_document_titles": ["Hand Hygiene SOP"],
    },
    {
        "question": "When is soap and water required instead of alcohol handrub?",
        "expected_document_titles": ["Hand Hygiene SOP"],
    },
    {
        "question": "Which procedures require insurance pre-authorization?",
        "expected_document_titles": ["Insurance Pre-Authorization Policy"],
    },
    {
        "question": "How long after discharge must the summary document be completed?",
        "expected_document_titles": ["Discharge Summary Documentation Guidelines"],
    },
]
