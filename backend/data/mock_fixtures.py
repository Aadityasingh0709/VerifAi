"""Expanded fabricated verification data for VerifAI demo.

Covers: French Revolution, Aspirin, JWST, CPU, sizeof, Grace Hopper bug myth,
P-N junction, MLA full forms, potato classification, India national fruit,
moon landing, Python language, DNA discovery, speed of light, gravity,
photosynthesis, Bitcoin, water/H2O, and more.

Each topic includes: claims, verdicts, sources, correct_information.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from backend.data.samples import (
    SAMPLE_1_HISTORY,
    SAMPLE_2_MEDICAL,
    SAMPLE_3_RESEARCH,
)


def _locate(doc: str, sentence: str) -> tuple[int, int]:
    idx = doc.find(sentence)
    if idx == -1:
        snippet = sentence[:30]
        idx = doc.find(snippet)
        if idx == -1:
            return (0, min(len(sentence), len(doc)))
    return (idx, idx + len(sentence))


# ==================================================================
# TOPIC-BASED FIXTURES (keyword-matched)
# ==================================================================
TOPIC_FIXTURES: List[dict] = [
    # TOPIC: CPU
    {
        "keywords": ["cpu", "central processing unit", "processor", "full form of cpu"],
        "claims": [
            {"claim_text": "CPU stands for Central Processing Unit", "claim_category": "general", "high_stakes": False, "source_sentence": "The full form of CPU is Central Processing Unit.", "verdict": "VERIFIED", "confidence": 97, "reasoning": "CPU universally stands for Central Processing Unit in computing. Confirmed by multiple authoritative sources.", "best_source_url": "https://www.britannica.com/technology/central-processing-unit", "best_source_quote": "CPU, principal part of any digital computer system.", "sources": [{"url": "https://www.britannica.com/technology/central-processing-unit", "title": "Central Processing Unit | Britannica", "snippet": "CPU, principal part of any digital computer system.", "source_tier": 2, "relevance_score": 0.97}, {"url": "https://en.wikipedia.org/wiki/Central_processing_unit", "title": "Central processing unit - Wikipedia", "snippet": "A central processing unit (CPU) is the most important processor in a given computer.", "source_tier": 2, "relevance_score": 0.95}]},
            {"claim_text": "The CPU is the primary component that performs most of the processing inside a computer", "claim_category": "general", "high_stakes": False, "source_sentence": "The CPU is the primary component that performs most of the processing inside the computer.", "verdict": "VERIFIED", "confidence": 95, "reasoning": "The CPU executes instructions for arithmetic, logic, control, and I/O operations.", "best_source_url": "https://en.wikipedia.org/wiki/Central_processing_unit", "best_source_quote": "The CPU carries out basic arithmetic, logic, controlling, and I/O operations.", "sources": [{"url": "https://en.wikipedia.org/wiki/Central_processing_unit", "title": "Central processing unit - Wikipedia", "snippet": "The CPU carries out basic arithmetic, logic, controlling, and input/output operations.", "source_tier": 2, "relevance_score": 0.96}]},
            {"claim_text": "The CPU is often referred to as the brain of a computer", "claim_category": "general", "high_stakes": False, "source_sentence": "Often referred to as the brain of a computer, the CPU is the primary component.", "verdict": "VERIFIED", "confidence": 93, "reasoning": "The 'brain of the computer' metaphor for CPU is widely used in computing education.", "best_source_url": "https://edu.gcfglobal.org/en/computerbasics/inside-a-computer/1/", "best_source_quote": "The CPU is often called the brain of the computer.", "sources": [{"url": "https://edu.gcfglobal.org/en/computerbasics/inside-a-computer/1/", "title": "Computer Basics: Inside a Computer", "snippet": "The CPU is often called the brain of the computer.", "source_tier": 3, "relevance_score": 0.90}]},
        ],
        "correct_information": "CPU stands for Central Processing Unit. It is the primary electronic circuitry within a computer that executes instructions comprising a computer program. The CPU performs basic arithmetic, logic, controlling, and input/output (I/O) operations. It is often called the 'brain' of the computer. Modern CPUs are microprocessors on a single integrated circuit chip.",
    },
    # TOPIC: sizeof in C
    {
        "keywords": ["sizeof", "compile-time", "runtime", "operator in c", "c programming sizeof"],
        "claims": [
            {"claim_text": "In C, sizeof is a compile-time operator", "claim_category": "scientific", "high_stakes": False, "source_sentence": "In C, sizeof is a compile-time operator.", "verdict": "VERIFIED", "confidence": 96, "reasoning": "sizeof is evaluated at compile time in C (except for VLAs in C99). The compiler replaces sizeof with a constant value.", "best_source_url": "https://en.cppreference.com/w/c/language/sizeof", "best_source_quote": "The sizeof operator yields the size in bytes, determined at compile time.", "sources": [{"url": "https://en.cppreference.com/w/c/language/sizeof", "title": "sizeof operator - cppreference.com", "snippet": "Except for VLAs, the result is a compile-time constant.", "source_tier": 2, "relevance_score": 0.98}, {"url": "https://en.wikipedia.org/wiki/Sizeof", "title": "Sizeof - Wikipedia", "snippet": "sizeof is a compile-time operator in C.", "source_tier": 2, "relevance_score": 0.95}]},
            {"claim_text": "The sizeof operator in C is evaluated at runtime like a function call", "claim_category": "scientific", "high_stakes": False, "source_sentence": "The sizeof operator in C is evaluated at runtime, just like a function call.", "verdict": "HALLUCINATED", "confidence": 95, "reasoning": "This is false. sizeof is a compile-time operator, NOT evaluated at runtime. The only exception is C99 VLAs.", "best_source_url": "https://en.cppreference.com/w/c/language/sizeof", "best_source_quote": "sizeof is a compile-time unary operator, not a runtime function.", "contradicting_detail": "sizeof is a compile-time operator, not a runtime function.", "sources": [{"url": "https://en.cppreference.com/w/c/language/sizeof", "title": "sizeof operator - cppreference.com", "snippet": "sizeof is a compile-time unary operator.", "source_tier": 2, "relevance_score": 0.98}], "genealogy": {"genealogy_type": "domain_confusion", "real_fact": "sizeof is a compile-time operator. The compiler replaces it with constant values before the program runs.", "mutation_explanation": "The AI confused sizeof with a runtime function call because sizeof uses parentheses.", "confidence_in_genealogy": 92}},
        ],
        "correct_information": "The sizeof operator in C is a COMPILE-TIME operator, NOT a runtime function. The compiler evaluates sizeof during compilation and replaces it with a constant value. The only exception is C99 Variable Length Arrays (VLAs), where sizeof may be evaluated at runtime.",
    },
    # TOPIC: Grace Hopper / Computer Bug
    {
        "keywords": ["grace hopper", "computer bug", "bug", "moth", "harvard mark", "coined"],
        "claims": [
            {"claim_text": "The term 'computer bug' was coined by Grace Hopper in 1947", "claim_category": "event", "high_stakes": False, "source_sentence": "The term 'computer bug' was coined in 1947 when Grace Hopper found a moth in the Harvard Mark II.", "verdict": "HALLUCINATED", "confidence": 88, "reasoning": "The term 'bug' predates Hopper. Thomas Edison used it in the 1870s. Hopper popularized the anecdote but did not coin the term.", "best_source_url": "https://en.wikipedia.org/wiki/Software_bug#History", "best_source_quote": "The term 'bug' was used in engineering since the 1870s.", "contradicting_detail": "Grace Hopper did NOT coin the term. Edison used it decades earlier.", "sources": [{"url": "https://en.wikipedia.org/wiki/Software_bug#History", "title": "Software bug - Wikipedia", "snippet": "The term 'bug' has been part of engineering jargon since the 1870s.", "source_tier": 2, "relevance_score": 0.94}], "genealogy": {"genealogy_type": "attribute_swap", "real_fact": "Hopper's team found a moth in 1947, but the term 'bug' was already used by Edison in the 1870s.", "mutation_explanation": "AI incorrectly attributed coining of 'bug' to Hopper.", "confidence_in_genealogy": 88}},
            {"claim_text": "Grace Hopper found a moth in the Harvard Mark II in 1947", "claim_category": "event", "high_stakes": False, "source_sentence": "Grace Hopper found a moth trapped in a relay of the Harvard Mark II.", "verdict": "VERIFIED", "confidence": 92, "reasoning": "The moth incident is documented. The logbook is preserved at the Smithsonian.", "best_source_url": "https://americanhistory.si.edu/collections/search/object/nmah_334663", "best_source_quote": "The 1947 logbook with the moth is at the Smithsonian.", "sources": [{"url": "https://americanhistory.si.edu/collections/search/object/nmah_334663", "title": "Computer Bug Log Book - Smithsonian", "snippet": "The 1947 logbook with the moth is preserved at the Smithsonian.", "source_tier": 1, "relevance_score": 0.96}]},
        ],
        "correct_information": "While Grace Hopper's team did find a real moth in the Harvard Mark II in 1947, she did NOT coin the term 'bug'. The term was used by engineers including Thomas Edison in the 1870s. Hopper popularized the story but the terminology predates her. The logbook is at the Smithsonian.",
    },
    # TOPIC: P-N Junction
    {
        "keywords": ["p-n junction", "pn junction", "forward bias", "depletion region", "semiconductor", "diode"],
        "claims": [
            {"claim_text": "Forward-bias voltage causes the depletion region to increase in width", "claim_category": "scientific", "high_stakes": False, "source_sentence": "In a P-N junction, applying a forward-bias voltage causes the depletion region to increase in width.", "verdict": "HALLUCINATED", "confidence": 97, "reasoning": "INCORRECT. Forward bias DECREASES depletion region width. The external voltage opposes the built-in potential, narrowing the depletion zone.", "best_source_url": "https://en.wikipedia.org/wiki/P%E2%80%93n_junction", "best_source_quote": "Under forward bias, the depletion region decreases in width.", "contradicting_detail": "Forward bias DECREASES depletion region, not increases it.", "sources": [{"url": "https://en.wikipedia.org/wiki/P%E2%80%93n_junction", "title": "P-N junction - Wikipedia", "snippet": "Under forward bias, the depletion region decreases in width.", "source_tier": 2, "relevance_score": 0.95}], "genealogy": {"genealogy_type": "attribute_swap", "real_fact": "Forward bias DECREASES depletion region. Reverse bias INCREASES it.", "mutation_explanation": "AI swapped effects of forward and reverse bias.", "confidence_in_genealogy": 95}},
        ],
        "correct_information": "In a P-N junction: FORWARD BIAS decreases depletion region width (allows current). REVERSE BIAS increases depletion region width (blocks current). The claim confuses forward and reverse bias effects.",
    },
    # TOPIC: MLA Full Forms
    {
        "keywords": ["mla", "full form", "member of legislative", "modern language association"],
        "claims": [
            {"claim_text": "MLA stands for Member of the Legislative Assembly in Indian politics", "claim_category": "general", "high_stakes": False, "source_sentence": "MLA stands for Member of the Legislative Assembly.", "verdict": "VERIFIED", "confidence": 96, "reasoning": "MLA is the standard abbreviation for Member of the Legislative Assembly in Indian legislatures.", "best_source_url": "https://en.wikipedia.org/wiki/Member_of_the_Legislative_Assembly_(India)", "best_source_quote": "A Member of the Legislative Assembly (MLA) is elected to the legislature of a state in India.", "sources": [{"url": "https://en.wikipedia.org/wiki/Member_of_the_Legislative_Assembly_(India)", "title": "MLA (India) - Wikipedia", "snippet": "Elected representative in Indian state legislatures.", "source_tier": 2, "relevance_score": 0.97}]},
            {"claim_text": "MLA stands for Modern Language Association in academia", "claim_category": "general", "high_stakes": False, "source_sentence": "MLA stands for Modern Language Association.", "verdict": "VERIFIED", "confidence": 95, "reasoning": "The Modern Language Association is widely known for the MLA citation style.", "best_source_url": "https://www.mla.org/", "best_source_quote": "The Modern Language Association of America.", "sources": [{"url": "https://www.mla.org/", "title": "Modern Language Association", "snippet": "Professional organization for scholars of language and literature.", "source_tier": 2, "relevance_score": 0.96}]},
        ],
        "correct_information": "MLA has multiple meanings: 1) Member of the Legislative Assembly (Indian politics), 2) Modern Language Association (academia/citation style), 3) Master Licensing Agreement (business/legal).",
    },
    # TOPIC: Potato
    {
        "keywords": ["potato", "vegetable", "tuber", "solanum", "starchy", "botanical"],
        "claims": [
            {"claim_text": "A potato is the tuber of the Solanum tuberosum plant", "claim_category": "scientific", "high_stakes": False, "source_sentence": "Botanically, a potato is the tuber of the Solanum tuberosum plant.", "verdict": "VERIFIED", "confidence": 98, "reasoning": "The potato (Solanum tuberosum) is a starchy tuber — an enlarged underground stem.", "best_source_url": "https://en.wikipedia.org/wiki/Potato", "best_source_quote": "The potato is a starchy food, a tuber of the plant Solanum tuberosum.", "sources": [{"url": "https://en.wikipedia.org/wiki/Potato", "title": "Potato - Wikipedia", "snippet": "The potato is a tuber of Solanum tuberosum.", "source_tier": 2, "relevance_score": 0.98}]},
            {"claim_text": "Potatoes are classified as starchy vegetables in culinary terms", "claim_category": "general", "high_stakes": False, "source_sentence": "Potatoes are classified as starchy vegetables.", "verdict": "VERIFIED", "confidence": 94, "reasoning": "In dietary guidelines, potatoes are categorized as starchy vegetables.", "best_source_url": "https://www.hsph.harvard.edu/nutritionsource/what-should-you-eat/vegetables-and-fruits/", "best_source_quote": "Potatoes are starchy vegetables.", "sources": [{"url": "https://www.hsph.harvard.edu/nutritionsource/what-should-you-eat/vegetables-and-fruits/", "title": "Harvard Nutrition Source", "snippet": "Potatoes are starchy vegetables.", "source_tier": 1, "relevance_score": 0.90}]},
            {"claim_text": "A tuber is a modified stem, not a root", "claim_category": "scientific", "high_stakes": False, "source_sentence": "A tuber is an enlarged, fleshy underground part of the plant's stem (not the root).", "verdict": "VERIFIED", "confidence": 95, "reasoning": "Tubers are modified stems with nodes ('eyes'), not roots.", "best_source_url": "https://en.wikipedia.org/wiki/Tuber", "best_source_quote": "A tuber develops from the stem of a plant.", "sources": [{"url": "https://en.wikipedia.org/wiki/Tuber", "title": "Tuber - Wikipedia", "snippet": "A tuber is an enlarged structure developing from the stem.", "source_tier": 2, "relevance_score": 0.95}]},
        ],
        "correct_information": "Potato: Botanically a TUBER (modified underground STEM, not a root) of Solanum tuberosum. Culinarily classified as a starchy vegetable. NOT a fruit (doesn't develop from flowers or contain seeds).",
    },
    # TOPIC: Moon Landing
    {
        "keywords": ["moon landing", "apollo 11", "neil armstrong", "buzz aldrin", "first man on moon"],
        "claims": [
            {"claim_text": "Neil Armstrong was the first person to walk on the Moon", "claim_category": "event", "high_stakes": False, "source_sentence": "Neil Armstrong was the first person to walk on the Moon.", "verdict": "VERIFIED", "confidence": 99, "reasoning": "Armstrong stepped onto the lunar surface on July 20, 1969, during Apollo 11.", "best_source_url": "https://www.nasa.gov/mission/apollo-11/", "best_source_quote": "Neil Armstrong became the first human to step on the lunar surface on July 20, 1969.", "sources": [{"url": "https://www.nasa.gov/mission/apollo-11/", "title": "Apollo 11 - NASA", "snippet": "Neil Armstrong became the first human on the Moon.", "source_tier": 1, "relevance_score": 0.99}]},
            {"claim_text": "Apollo 11 landed on the Moon on July 20, 1969", "claim_category": "event", "high_stakes": False, "source_sentence": "Apollo 11 landed on the Moon on July 20, 1969.", "verdict": "VERIFIED", "confidence": 99, "reasoning": "The Eagle landed in the Sea of Tranquility on July 20, 1969.", "best_source_url": "https://www.nasa.gov/mission/apollo-11/", "best_source_quote": "Eagle landed on July 20, 1969, at 20:17 UTC.", "sources": [{"url": "https://www.nasa.gov/mission/apollo-11/", "title": "Apollo 11 - NASA", "snippet": "Landed July 20, 1969.", "source_tier": 1, "relevance_score": 0.99}]},
        ],
        "correct_information": "Apollo 11 landed on the Moon on July 20, 1969. Neil Armstrong was first to walk on the surface, followed by Buzz Aldrin. Michael Collins orbited above. Armstrong's words: 'That's one small step for man, one giant leap for mankind.'",
    },
    # TOPIC: Python
    {
        "keywords": ["python", "programming language", "guido van rossum", "interpreted"],
        "claims": [
            {"claim_text": "Python was created by Guido van Rossum", "claim_category": "person", "high_stakes": False, "source_sentence": "Python was created by Guido van Rossum.", "verdict": "VERIFIED", "confidence": 98, "reasoning": "Guido van Rossum created Python, first released in 1991.", "best_source_url": "https://en.wikipedia.org/wiki/Python_(programming_language)", "best_source_quote": "Conceived by Guido van Rossum at CWI in the Netherlands.", "sources": [{"url": "https://en.wikipedia.org/wiki/Python_(programming_language)", "title": "Python - Wikipedia", "snippet": "Conceived by Guido van Rossum.", "source_tier": 2, "relevance_score": 0.98}]},
            {"claim_text": "Python is an interpreted, high-level programming language", "claim_category": "scientific", "high_stakes": False, "source_sentence": "Python is an interpreted, high-level programming language.", "verdict": "VERIFIED", "confidence": 96, "reasoning": "Python is widely classified as interpreted and high-level.", "best_source_url": "https://www.python.org/about/", "best_source_quote": "Python lets you work quickly and integrate systems effectively.", "sources": [{"url": "https://www.python.org/about/", "title": "About Python", "snippet": "High-level programming language.", "source_tier": 2, "relevance_score": 0.95}]},
        ],
        "correct_information": "Python is a high-level, interpreted, general-purpose programming language created by Guido van Rossum, first released in 1991. It emphasizes code readability and supports multiple paradigms.",
    },
    # TOPIC: DNA
    {
        "keywords": ["dna", "double helix", "watson", "crick", "deoxyribonucleic", "rosalind franklin"],
        "claims": [
            {"claim_text": "DNA structure was discovered by Watson and Crick in 1953", "claim_category": "scientific", "high_stakes": False, "source_sentence": "The structure of DNA was discovered by Watson and Crick in 1953.", "verdict": "VERIFIED", "confidence": 90, "reasoning": "Watson and Crick published the double helix model in Nature in 1953. Rosalind Franklin's X-ray work was crucial but often underacknowledged.", "best_source_url": "https://www.nature.com/articles/171737a0", "best_source_quote": "Watson and Crick proposed the double helix in 1953.", "sources": [{"url": "https://www.nature.com/articles/171737a0", "title": "Molecular Structure of Nucleic Acids - Nature", "snippet": "Watson and Crick proposed the double helix in 1953.", "source_tier": 1, "relevance_score": 0.98}]},
            {"claim_text": "DNA stands for deoxyribonucleic acid", "claim_category": "scientific", "high_stakes": False, "source_sentence": "DNA stands for deoxyribonucleic acid.", "verdict": "VERIFIED", "confidence": 99, "reasoning": "Universally accepted abbreviation.", "best_source_url": "https://www.genome.gov/genetics-glossary/Deoxyribonucleic-Acid", "best_source_quote": "DNA, or deoxyribonucleic acid, is the hereditary material.", "sources": [{"url": "https://www.genome.gov/genetics-glossary/Deoxyribonucleic-Acid", "title": "DNA - NIH", "snippet": "DNA is the hereditary material.", "source_tier": 1, "relevance_score": 0.99}]},
        ],
        "correct_information": "DNA (deoxyribonucleic acid) double helix structure was proposed by Watson and Crick in 1953. Rosalind Franklin's X-ray crystallography (Photo 51) was crucial. Watson, Crick, and Wilkins received the 1962 Nobel Prize.",
    },
    # TOPIC: Speed of Light
    {
        "keywords": ["speed of light", "light speed", "299", "3 x 10", "vacuum"],
        "claims": [
            {"claim_text": "The speed of light in vacuum is approximately 299,792,458 m/s", "claim_category": "scientific", "high_stakes": False, "source_sentence": "The speed of light in a vacuum is approximately 299,792,458 meters per second.", "verdict": "VERIFIED", "confidence": 99, "reasoning": "Exactly 299,792,458 m/s by definition since 1983.", "best_source_url": "https://physics.nist.gov/cgi-bin/cuu/Value?c", "best_source_quote": "c = 299,792,458 m/s (exact).", "sources": [{"url": "https://physics.nist.gov/cgi-bin/cuu/Value?c", "title": "Speed of Light - NIST", "snippet": "c = 299,792,458 m/s (exact).", "source_tier": 1, "relevance_score": 0.99}]},
        ],
        "correct_information": "Speed of light in vacuum: exactly 299,792,458 m/s (~3 x 10^8 m/s). Since 1983, the meter is defined by this constant.",
    },
    # TOPIC: Photosynthesis
    {
        "keywords": ["photosynthesis", "chlorophyll", "carbon dioxide", "glucose", "sunlight", "oxygen"],
        "claims": [
            {"claim_text": "Photosynthesis converts sunlight into chemical energy", "claim_category": "scientific", "high_stakes": False, "source_sentence": "Photosynthesis is the process by which plants convert sunlight into chemical energy.", "verdict": "VERIFIED", "confidence": 97, "reasoning": "6CO2 + 6H2O + light -> C6H12O6 + 6O2.", "best_source_url": "https://www.britannica.com/science/photosynthesis", "best_source_quote": "Green plants transform light energy into chemical energy.", "sources": [{"url": "https://www.britannica.com/science/photosynthesis", "title": "Photosynthesis | Britannica", "snippet": "Plants transform light energy into chemical energy.", "source_tier": 2, "relevance_score": 0.98}]},
        ],
        "correct_information": "Photosynthesis: 6CO2 + 6H2O + light -> C6H12O6 + 6O2. Occurs in chloroplasts using chlorophyll. Two stages: light-dependent reactions and Calvin cycle.",
    },
    # TOPIC: Bitcoin
    {
        "keywords": ["bitcoin", "satoshi nakamoto", "cryptocurrency", "blockchain", "btc"],
        "claims": [
            {"claim_text": "Bitcoin was created by Satoshi Nakamoto", "claim_category": "event", "high_stakes": False, "source_sentence": "Bitcoin was created by Satoshi Nakamoto.", "verdict": "VERIFIED", "confidence": 95, "reasoning": "Whitepaper published 2008, network live January 3, 2009.", "best_source_url": "https://en.wikipedia.org/wiki/Bitcoin", "best_source_quote": "Invented by unknown person using pseudonym Satoshi Nakamoto.", "sources": [{"url": "https://en.wikipedia.org/wiki/Bitcoin", "title": "Bitcoin - Wikipedia", "snippet": "Invented by Satoshi Nakamoto. Network live January 3, 2009.", "source_tier": 2, "relevance_score": 0.97}]},
        ],
        "correct_information": "Bitcoin: decentralized cryptocurrency created by pseudonymous Satoshi Nakamoto. Whitepaper October 31, 2008. Network live January 3, 2009 (genesis block). True identity unknown.",
    },
    # TOPIC: Gravity
    {
        "keywords": ["gravity", "newton", "gravitational", "9.8", "acceleration due to"],
        "claims": [
            {"claim_text": "Acceleration due to gravity on Earth is approximately 9.8 m/s^2", "claim_category": "scientific", "high_stakes": False, "source_sentence": "The acceleration due to gravity on Earth's surface is approximately 9.8 m/s squared.", "verdict": "VERIFIED", "confidence": 98, "reasoning": "Standard gravity: 9.80665 m/s^2. Varies slightly by location.", "best_source_url": "https://physics.nist.gov/cgi-bin/cuu/Value?gn", "best_source_quote": "gn = 9.80665 m/s^2.", "sources": [{"url": "https://physics.nist.gov/cgi-bin/cuu/Value?gn", "title": "Standard Gravity - NIST", "snippet": "gn = 9.80665 m/s^2.", "source_tier": 1, "relevance_score": 0.99}]},
        ],
        "correct_information": "Standard acceleration due to gravity: 9.80665 m/s^2 (~9.8 m/s^2). Varies from ~9.78 (equator) to ~9.83 (poles). Newton's law of gravitation published 1687.",
    },
    # TOPIC: Water
    {
        "keywords": ["water", "h2o", "boiling point", "freezing point", "chemical formula"],
        "claims": [
            {"claim_text": "Water has the chemical formula H2O", "claim_category": "scientific", "high_stakes": False, "source_sentence": "Water has the chemical formula H2O.", "verdict": "VERIFIED", "confidence": 99, "reasoning": "Two hydrogen atoms bonded to one oxygen atom.", "best_source_url": "https://en.wikipedia.org/wiki/Water", "best_source_quote": "Water is an inorganic compound with formula H2O.", "sources": [{"url": "https://en.wikipedia.org/wiki/Water", "title": "Water - Wikipedia", "snippet": "Chemical formula H2O.", "source_tier": 2, "relevance_score": 0.99}]},
            {"claim_text": "Water boils at 100 degrees Celsius at standard pressure", "claim_category": "scientific", "high_stakes": False, "source_sentence": "Water boils at 100 degrees Celsius.", "verdict": "VERIFIED", "confidence": 98, "reasoning": "At 1 atm, water boils at 100C (212F).", "best_source_url": "https://en.wikipedia.org/wiki/Properties_of_water", "best_source_quote": "Boils at 100C at 1 atm.", "sources": [{"url": "https://en.wikipedia.org/wiki/Properties_of_water", "title": "Properties of water - Wikipedia", "snippet": "Boils at 100C at standard pressure.", "source_tier": 2, "relevance_score": 0.98}]},
        ],
        "correct_information": "Water (H2O): 2 hydrogen + 1 oxygen. Boiling point 100C (212F) at 1 atm. Freezing point 0C (32F). Universal solvent. Three states: solid, liquid, gas.",
    },
    # TOPIC: India National Fruit
    {
        "keywords": ["india", "national fruit", "mango"],
        "claims": [
            {"claim_text": "The national fruit of India is the mango", "claim_category": "general", "high_stakes": False, "source_sentence": "The national fruit of India is the mango.", "verdict": "VERIFIED", "confidence": 97, "reasoning": "Officially recognized by the Government of India.", "best_source_url": "https://knowindia.india.gov.in/national-identity-elements/national-fruit.php", "best_source_quote": "The National Fruit of India is Mango.", "sources": [{"url": "https://knowindia.india.gov.in/national-identity-elements/national-fruit.php", "title": "National Fruit - Know India (.gov)", "snippet": "The National Fruit of India is Mango.", "source_tier": 1, "relevance_score": 0.99}]},
        ],
        "correct_information": "The national fruit of India is the Mango (Mangifera indica). India is the largest producer of mangoes globally (~45% of world production).",
    },
    # ==================================================================
    # HALLUCINATION TRAP TOPICS — questions with NO real answer
    # Any factual-sounding AI reply = HALLUCINATED
    # ==================================================================
    # TRAP: Nobel Prize 2027 (future event)
    {
        "keywords": ["nobel prize 2027", "nobel 2027", "prize in 2027"],
        "claims": [
            {"claim_text": "Someone won the Nobel Prize in Physics in 2027", "claim_category": "event", "high_stakes": False, "source_sentence": "won the Nobel Prize in Physics in 2027", "verdict": "HALLUCINATED", "confidence": 99, "reasoning": "The Nobel Prize for 2027 has not been awarded yet. Any answer naming a winner is fabricated.", "best_source_url": "https://www.nobelprize.org/", "best_source_quote": "Nobel Prizes for 2027 have not yet been announced.", "contradicting_detail": "2027 Nobel Prizes have NOT been announced. This is a future event — any named winner is hallucinated.", "sources": [{"url": "https://www.nobelprize.org/", "title": "NobelPrize.org", "snippet": "Official source for Nobel Prize announcements.", "source_tier": 1, "relevance_score": 0.99}], "genealogy": {"genealogy_type": "pure_confabulation", "real_fact": "The 2027 Nobel Prizes have not been awarded yet.", "mutation_explanation": "AI fabricated a winner for a future event because it tries to always provide a complete answer rather than admitting uncertainty.", "confidence_in_genealogy": 99}},
        ],
        "correct_information": "The Nobel Prize in Physics for 2027 has NOT been awarded yet. Any AI claiming a specific winner is hallucinating. This is a classic hallucination trap — AI models try to complete patterns rather than saying 'I don't know.' Always verify time-sensitive claims against official sources like nobelprize.org.",
    },
    # TRAP: iPhone 20 (non-existent product)
    {
        "keywords": ["iphone 20", "features of iphone 20", "apple iphone 20"],
        "claims": [
            {"claim_text": "The iPhone 20 has specific features or specifications", "claim_category": "general", "high_stakes": False, "source_sentence": "iPhone 20", "verdict": "HALLUCINATED", "confidence": 98, "reasoning": "iPhone 20 does not exist. Apple has not announced this product. Any listed features are fabricated.", "best_source_url": "https://www.apple.com/iphone/", "best_source_quote": "Apple's current iPhone lineup does not include an iPhone 20.", "contradicting_detail": "iPhone 20 does not exist. Apple has not released or announced this product.", "sources": [{"url": "https://www.apple.com/iphone/", "title": "iPhone - Apple", "snippet": "Apple's current iPhone lineup.", "source_tier": 1, "relevance_score": 0.95}], "genealogy": {"genealogy_type": "pure_confabulation", "real_fact": "iPhone 20 does not exist as of 2025.", "mutation_explanation": "AI extrapolated from existing iPhone models and invented features for a non-existent product.", "confidence_in_genealogy": 98}},
        ],
        "correct_information": "iPhone 20 DOES NOT EXIST. Apple has not announced or released any product called iPhone 20. Any AI describing its 'features' or 'specs' is hallucinating by extrapolating from existing products. This demonstrates the 'pattern completion' hallucination — models extend sequences (iPhone 14, 15, 16...) and invent plausible-sounding but fake details.",
    },
    # TRAP: Quantum Neural Blockchain Fusion (fake concept)
    {
        "keywords": ["quantum neural blockchain", "blockchain fusion algorithm", "hyperbolic time gravity"],
        "claims": [
            {"claim_text": "Quantum Neural Blockchain Fusion Algorithm is a real concept", "claim_category": "scientific", "high_stakes": False, "source_sentence": "Quantum Neural Blockchain Fusion", "verdict": "HALLUCINATED", "confidence": 99, "reasoning": "This is a completely fabricated term. No such algorithm or concept exists in any scientific literature.", "best_source_url": "https://scholar.google.com/", "best_source_quote": "No results found for 'Quantum Neural Blockchain Fusion Algorithm'.", "contradicting_detail": "This concept does not exist. It was invented by combining real buzzwords (quantum + neural + blockchain) into a fake term.", "sources": [{"url": "https://scholar.google.com/", "title": "Google Scholar", "snippet": "No academic papers match this term.", "source_tier": 1, "relevance_score": 0.99}], "genealogy": {"genealogy_type": "amalgamation", "real_fact": "Quantum computing, neural networks, and blockchain are separate real fields. No 'fusion algorithm' combines them.", "mutation_explanation": "AI combined real buzzwords into a fake concept and generated a plausible-sounding explanation because it prioritizes fluency over accuracy.", "confidence_in_genealogy": 99}},
        ],
        "correct_information": "'Quantum Neural Blockchain Fusion Algorithm' is a COMPLETELY FAKE term. It does not exist in any scientific literature. AI models hallucinate definitions for invented terms because they are trained to sound confident and complete. This is called 'amalgamation hallucination' — combining real concepts (quantum, neural, blockchain) into a non-existent one.",
    },
    # TRAP: Oxygen on Mars (false premise)
    {
        "keywords": ["discovered oxygen on mars", "oxygen on mars", "who discovered oxygen mars"],
        "claims": [
            {"claim_text": "Someone discovered oxygen on Mars", "claim_category": "scientific", "high_stakes": False, "source_sentence": "discovered oxygen on Mars", "verdict": "HALLUCINATED", "confidence": 97, "reasoning": "No one has 'discovered oxygen on Mars' in the way the question implies. Mars atmosphere is 95% CO2 with only trace oxygen (0.13%).", "best_source_url": "https://www.nasa.gov/mars", "best_source_quote": "Mars atmosphere is about 95.3% carbon dioxide.", "contradicting_detail": "Mars has only 0.13% atmospheric oxygen. No one 'discovered' oxygen on Mars — the question contains a false premise.", "sources": [{"url": "https://www.nasa.gov/mars", "title": "Mars - NASA", "snippet": "95% CO2 atmosphere.", "source_tier": 1, "relevance_score": 0.97}], "genealogy": {"genealogy_type": "pure_confabulation", "real_fact": "Mars atmosphere is 95.3% CO2. MOXIE experiment produced small amounts of O2 from CO2 but nobody 'discovered' oxygen there.", "mutation_explanation": "AI accepted a false premise and fabricated a discoverer rather than challenging the question.", "confidence_in_genealogy": 96}},
        ],
        "correct_information": "Nobody 'discovered oxygen on Mars.' Mars has only trace oxygen (0.13%) in its CO2-dominated atmosphere. NASA's MOXIE experiment on Perseverance rover demonstrated extracting O2 from CO2, but this is manufacturing, not discovery. When AI models accept false premises without questioning them, they build hallucinated answers on wrong foundations.",
    },
    # TRAP: Google Neptune API (fake product)
    {
        "keywords": ["google neptune api", "neptune api 2026", "google neptune"],
        "claims": [
            {"claim_text": "Google Neptune API exists or was released", "claim_category": "general", "high_stakes": False, "source_sentence": "Google Neptune API", "verdict": "HALLUCINATED", "confidence": 99, "reasoning": "There is no Google product called 'Neptune API'. This is a fabricated product name.", "best_source_url": "https://cloud.google.com/products", "best_source_quote": "No product called Neptune API exists in Google Cloud.", "contradicting_detail": "Google Neptune API does not exist. No such product has been announced or released by Google.", "sources": [{"url": "https://cloud.google.com/products", "title": "Google Cloud Products", "snippet": "Full list of Google Cloud products and services.", "source_tier": 1, "relevance_score": 0.95}], "genealogy": {"genealogy_type": "pure_confabulation", "real_fact": "Google has no product called Neptune API. Amazon has Neptune (graph DB), which may cause confusion.", "mutation_explanation": "AI likely confused Amazon Neptune with Google, or simply invented a plausible-sounding Google product name.", "confidence_in_genealogy": 97}},
        ],
        "correct_information": "'Google Neptune API' DOES NOT EXIST. There is no Google product by this name. Amazon has a graph database called Amazon Neptune, which may cause confusion. AI models fabricate product details for non-existent tools because they pattern-match company names with plausible product names.",
    },
    # TRAP: Einstein's 1935 paper on quantum AI (fake citation)
    {
        "keywords": ["einstein 1935 quantum ai", "einstein paper quantum ai", "einstein quantum artificial intelligence"],
        "claims": [
            {"claim_text": "Einstein wrote a paper on quantum AI in 1935", "claim_category": "citation", "high_stakes": False, "source_sentence": "Einstein's 1935 paper on quantum AI", "verdict": "HALLUCINATED", "confidence": 99, "reasoning": "Einstein never wrote about 'quantum AI'. His famous 1935 paper is the EPR paradox paper on quantum entanglement, not artificial intelligence.", "best_source_url": "https://en.wikipedia.org/wiki/EPR_paradox", "best_source_quote": "The 1935 EPR paper discussed quantum entanglement, not AI.", "contradicting_detail": "Einstein's 1935 paper was the EPR paradox paper about quantum entanglement. AI did not exist as a field until 1956.", "sources": [{"url": "https://en.wikipedia.org/wiki/EPR_paradox", "title": "EPR paradox - Wikipedia", "snippet": "Einstein, Podolsky, Rosen 1935 paper on quantum mechanics.", "source_tier": 2, "relevance_score": 0.95}], "genealogy": {"genealogy_type": "amalgamation", "real_fact": "Einstein's 1935 paper is the EPR paradox. AI as a field was founded in 1956 at the Dartmouth Conference.", "mutation_explanation": "AI merged 'Einstein + 1935 + quantum' (real) with 'AI' (unrelated) to fabricate a non-existent paper.", "confidence_in_genealogy": 98}},
        ],
        "correct_information": "Einstein NEVER wrote about 'quantum AI'. His famous 1935 paper is the EPR paradox (Einstein-Podolsky-Rosen), which deals with quantum entanglement, NOT artificial intelligence. AI as a field wasn't founded until 1956 at the Dartmouth Conference. This is a classic 'fake citation' hallucination — AI models generate plausible-sounding but non-existent academic references.",
    },
    # TRAP: India lost 2024 T20 World Cup (false assumption)
    {
        "keywords": ["india lost 2024 t20", "india lose t20 world cup 2024", "india lost t20 final"],
        "claims": [
            {"claim_text": "India lost the 2024 T20 World Cup final", "claim_category": "event", "high_stakes": False, "source_sentence": "India lost the 2024 T20 World Cup", "verdict": "HALLUCINATED", "confidence": 99, "reasoning": "INCORRECT. India WON the 2024 ICC T20 World Cup, defeating South Africa in the final in Barbados.", "best_source_url": "https://www.icc-cricket.com/", "best_source_quote": "India won the 2024 T20 World Cup.", "contradicting_detail": "India WON the 2024 T20 World Cup. They beat South Africa by 7 runs in the final at Barbados.", "sources": [{"url": "https://www.icc-cricket.com/", "title": "ICC Cricket", "snippet": "India won the 2024 T20 World Cup.", "source_tier": 1, "relevance_score": 0.99}], "genealogy": {"genealogy_type": "attribute_swap", "real_fact": "India WON the 2024 T20 World Cup final against South Africa by 7 runs in Barbados on June 29, 2024.", "mutation_explanation": "AI accepted the false premise in the question ('Why did India lose?') instead of correcting it, then built an explanation around a wrong fact.", "confidence_in_genealogy": 99}},
        ],
        "correct_information": "India DID NOT lose the 2024 T20 World Cup. India WON the 2024 ICC T20 World Cup, defeating South Africa by 7 runs in the final at Kensington Oval, Barbados on June 29, 2024. This is a 'trick question' hallucination — when a question contains a false assumption, AI models often accept the wrong premise and build answers on it instead of correcting it.",
    },
    # TRAP: Deep Learning in Mars Colonies paper (fake paper)
    {
        "keywords": ["deep learning mars colonies", "paper mars colonies 1999", "mars colonies paper"],
        "claims": [
            {"claim_text": "A paper called 'Deep Learning in Mars Colonies' exists", "claim_category": "citation", "high_stakes": False, "source_sentence": "Deep Learning in Mars Colonies", "verdict": "HALLUCINATED", "confidence": 99, "reasoning": "This paper does not exist. Deep learning emerged in the 2010s, and there are no Mars colonies. A 1999 paper on this topic is impossible.", "best_source_url": "https://scholar.google.com/", "best_source_quote": "No results for this paper title.", "contradicting_detail": "This paper does not exist. Deep learning wasn't a field in 1999, and Mars colonies don't exist.", "sources": [{"url": "https://scholar.google.com/", "title": "Google Scholar", "snippet": "No matching papers found.", "source_tier": 1, "relevance_score": 0.99}], "genealogy": {"genealogy_type": "pure_confabulation", "real_fact": "Deep learning emerged around 2012 (AlexNet). No Mars colonies exist. A 1999 paper combining both is impossible.", "mutation_explanation": "AI fabricated authors, journal name, and summary for a completely non-existent paper because models are trained to provide complete answers.", "confidence_in_genealogy": 99}},
        ],
        "correct_information": "'Deep Learning in Mars Colonies (1999)' is a COMPLETELY FAKE paper. Deep learning as a field emerged around 2012, and no Mars colonies exist. AI models are notorious for fabricating academic citations — generating fake author names, fake journal titles, and fake summaries that look convincing but are entirely made up.",
    },
    # TRAP: Jaguar ambiguity test
    {
        "keywords": ["tell me about jaguar", "jaguar"],
        "claims": [
            {"claim_text": "Jaguar refers to a specific single entity without clarification", "claim_category": "general", "high_stakes": False, "source_sentence": "Tell me about Jaguar", "verdict": "UNVERIFIED", "confidence": 40, "reasoning": "'Jaguar' is ambiguous — it could refer to the animal (Panthera onca), the car brand (Jaguar Land Rover), or Apple's macOS Jaguar (10.2). Without context, any single interpretation may be wrong.", "best_source_url": "https://en.wikipedia.org/wiki/Jaguar_(disambiguation)", "best_source_quote": "Jaguar may refer to multiple entities.", "sources": [{"url": "https://en.wikipedia.org/wiki/Jaguar_(disambiguation)", "title": "Jaguar (disambiguation) - Wikipedia", "snippet": "Multiple meanings: animal, car, OS, etc.", "source_tier": 2, "relevance_score": 0.85}]},
        ],
        "correct_information": "'Jaguar' is AMBIGUOUS. It can mean: 1) Panthera onca — the big cat native to the Americas, 2) Jaguar Cars — British luxury vehicle manufacturer (now Jaguar Land Rover), 3) macOS Jaguar — Apple's Mac OS X 10.2 (2002). AI models often pick one meaning confidently without acknowledging the ambiguity, which can mislead users.",
    },
]


# ==================================================================
# LEGACY SAMPLE FIXTURES
# ==================================================================
SAMPLE_1_CLAIMS = [
    {"claim_text": "The French Revolution began in 1789", "claim_category": "event", "high_stakes": False, "source_sentence": "The French Revolution began in 1789 when King Louis XVI called an emergency meeting of the Estates-General to address the financial crisis.", "verdict": "VERIFIED", "confidence": 98, "reasoning": "Multiple sources confirm the revolution began in 1789.", "best_source_url": "https://www.britannica.com/event/French-Revolution", "best_source_quote": "Revolutionary movement between 1787 and 1799.", "sources": [{"url": "https://www.britannica.com/event/French-Revolution", "title": "French Revolution | Britannica", "snippet": "Revolutionary movement between 1787 and 1799.", "source_tier": 2, "relevance_score": 0.95}]},
    {"claim_text": "The Bastille freed 723 political prisoners", "claim_category": "statistical", "high_stakes": False, "source_sentence": "The storming of the Bastille on July 14, 1789 marked a turning point, as it freed 723 political prisoners who had been held there for decades.", "verdict": "HALLUCINATED", "confidence": 96, "reasoning": "Only 7 prisoners were held. 723 is fabricated.", "best_source_url": "https://www.britannica.com/event/storming-of-the-Bastille", "best_source_quote": "Only seven inmates were found inside.", "contradicting_detail": "Only 7 prisoners, not 723.", "sources": [{"url": "https://www.britannica.com/event/storming-of-the-Bastille", "title": "Storming of the Bastille | Britannica", "snippet": "Only seven inmates found inside.", "source_tier": 2, "relevance_score": 0.98}], "genealogy": {"genealogy_type": "attribute_swap", "real_fact": "Only 7 prisoners.", "mutation_explanation": "Fabricated three-digit number.", "confidence_in_genealogy": 82}},
    {"claim_text": "Marie Antoinette said 'Let them eat cake'", "claim_category": "citation", "high_stakes": False, "source_sentence": "Marie Antoinette famously said \"Let them eat cake\" in response to news of the bread shortages.", "verdict": "HALLUCINATED", "confidence": 88, "reasoning": "Quote predates Antoinette. Rousseau used it in 1767.", "best_source_url": "https://www.britannica.com/biography/Marie-Antoinette-queen-of-France", "best_source_quote": "No evidence she said it.", "contradicting_detail": "Misattributed quote from Rousseau (1767).", "sources": [{"url": "https://www.britannica.com/biography/Marie-Antoinette-queen-of-France", "title": "Marie Antoinette | Britannica", "snippet": "No evidence she said it.", "source_tier": 2, "relevance_score": 0.89}], "genealogy": {"genealogy_type": "attribute_swap", "real_fact": "From Rousseau's Confessions (1767).", "mutation_explanation": "Reassigned to more famous figure.", "confidence_in_genealogy": 90}},
    {"claim_text": "Declaration of Rights of Man drafted by Thomas Jefferson", "claim_category": "citation", "high_stakes": False, "source_sentence": "The revolution ultimately led to the Declaration of the Rights of Man, drafted primarily by Thomas Jefferson during his time in Paris as US ambassador.", "verdict": "HALLUCINATED", "confidence": 92, "reasoning": "Drafted by Lafayette, not Jefferson.", "best_source_url": "https://www.britannica.com/topic/Declaration-of-the-Rights-of-Man-and-of-the-Citizen", "best_source_quote": "Drafted by Lafayette, who consulted Jefferson.", "contradicting_detail": "Lafayette was the drafter, not Jefferson.", "sources": [{"url": "https://www.britannica.com/topic/Declaration-of-the-Rights-of-Man-and-of-the-Citizen", "title": "Declaration | Britannica", "snippet": "Drafted by Lafayette.", "source_tier": 2, "relevance_score": 0.96}], "genealogy": {"genealogy_type": "attribute_swap", "real_fact": "Lafayette drafted it, consulting Jefferson.", "mutation_explanation": "Reversed roles.", "confidence_in_genealogy": 88}},
]

SAMPLE_2_CLAIMS = [
    {"claim_text": "Aspirin synthesized by Hoffmann at Bayer in 1897", "claim_category": "scientific", "high_stakes": False, "source_sentence": "Aspirin (acetylsalicylic acid) was first synthesized by Felix Hoffmann at Bayer in 1897.", "verdict": "VERIFIED", "confidence": 92, "reasoning": "Widely accepted historical fact.", "best_source_url": "https://pubmed.ncbi.nlm.nih.gov/10949246/", "best_source_quote": "Hoffmann synthesized acetylsalicylic acid in 1897.", "sources": [{"url": "https://pubmed.ncbi.nlm.nih.gov/10949246/", "title": "History of aspirin - PubMed", "snippet": "Hoffmann synthesized it in 1897.", "source_tier": 1, "relevance_score": 0.93}]},
    {"claim_text": "Aspirin reduces heart attack risk by 44%", "claim_category": "medical", "high_stakes": True, "source_sentence": "Clinical studies have shown that a daily low-dose aspirin of 81mg reduces the risk of heart attack by approximately 44% in adults over 50.", "verdict": "HALLUCINATED", "confidence": 89, "reasoning": "Outdated 1989 figure. Modern guidance disagrees.", "best_source_url": "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/aspirin-to-prevent-cardiovascular-disease-preventive-medication", "best_source_quote": "No net benefit for primary prevention in adults 60+.", "contradicting_detail": "44% is outdated (1989 male-only study).", "sources": [{"url": "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/aspirin-to-prevent-cardiovascular-disease-preventive-medication", "title": "USPSTF Aspirin", "snippet": "No net benefit for adults 60+.", "source_tier": 1, "relevance_score": 0.95}], "genealogy": {"genealogy_type": "temporal_drift", "real_fact": "1989 male-only study.", "mutation_explanation": "Outdated figure applied broadly.", "confidence_in_genealogy": 85}},
    {"claim_text": "WHO classifies aspirin as essential medicine", "claim_category": "medical", "high_stakes": False, "source_sentence": "The WHO classifies aspirin as an essential medicine.", "verdict": "VERIFIED", "confidence": 95, "reasoning": "On WHO Essential Medicines list.", "best_source_url": "https://www.who.int/publications/i/item/WHO-MHP-HPS-EML-2023.02", "best_source_quote": "Acetylsalicylic acid is listed.", "sources": [{"url": "https://www.who.int/publications/i/item/WHO-MHP-HPS-EML-2023.02", "title": "WHO Essential Medicines", "snippet": "Listed.", "source_tier": 1, "relevance_score": 0.97}]},
]

SAMPLE_3_CLAIMS = [
    {"claim_text": "JWST launched December 25, 2021", "claim_category": "event", "high_stakes": False, "source_sentence": "The James Webb Space Telescope (JWST) launched on December 25, 2021.", "verdict": "VERIFIED", "confidence": 99, "reasoning": "Confirmed by NASA.", "best_source_url": "https://www.nasa.gov/mission/webb/", "best_source_quote": "Launched December 25, 2021.", "sources": [{"url": "https://www.nasa.gov/mission/webb/", "title": "JWST - NASA", "snippet": "Launched December 25, 2021.", "source_tier": 1, "relevance_score": 0.98}]},
    {"claim_text": "JWST is a joint project of NASA, ESA, and CSA", "claim_category": "general", "high_stakes": False, "source_sentence": "It is a joint project of NASA, the European Space Agency, and the Canadian Space Agency.", "verdict": "VERIFIED", "confidence": 98, "reasoning": "All three agencies confirmed.", "best_source_url": "https://www.nasa.gov/mission/webb/", "best_source_quote": "International partnership with ESA and CSA.", "sources": [{"url": "https://www.nasa.gov/mission/webb/", "title": "JWST - NASA", "snippet": "Partnership with ESA and CSA.", "source_tier": 1, "relevance_score": 0.97}]},
    {"claim_text": "JWST primary mirror: 18 hexagonal beryllium segments, 6.5m", "claim_category": "scientific", "high_stakes": False, "source_sentence": "Its primary mirror is composed of 18 hexagonal gold-coated beryllium segments, totaling 6.5 meters in diameter.", "verdict": "VERIFIED", "confidence": 99, "reasoning": "NASA confirms.", "best_source_url": "https://webb.nasa.gov/content/observatory/ote/mirrors/index.html", "best_source_quote": "18 beryllium segments, gold-coated, 6.5m.", "sources": [{"url": "https://webb.nasa.gov/content/observatory/ote/mirrors/index.html", "title": "JWST Mirrors - NASA", "snippet": "18 segments, 6.5m.", "source_tier": 1, "relevance_score": 0.98}]},
]

SAMPLE_FIXTURES = {
    "sample1": {"text": SAMPLE_1_HISTORY, "claims": SAMPLE_1_CLAIMS},
    "sample2": {"text": SAMPLE_2_MEDICAL, "claims": SAMPLE_2_CLAIMS},
    "sample3": {"text": SAMPLE_3_RESEARCH, "claims": SAMPLE_3_CLAIMS},
}


# ==================================================================
# MATCHING ENGINE
# ==================================================================
def _match_score(text: str, keywords: List[str]) -> int:
    lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in lower)


def get_fixture_for_text(text: str) -> Optional[Dict]:
    """Match text against fixtures."""
    # Exact/prefix match with samples
    for sid, fixture in SAMPLE_FIXTURES.items():
        if text.strip() == fixture["text"].strip():
            return fixture
    for sid, fixture in SAMPLE_FIXTURES.items():
        sample_start = fixture["text"].strip()[:80]
        if sample_start and sample_start in text:
            return fixture

    # Keyword match against topics
    best_topic = None
    best_score = 0
    for topic in TOPIC_FIXTURES:
        score = _match_score(text, topic["keywords"])
        if score > best_score:
            best_score = score
            best_topic = topic

    if best_topic and best_score >= 1:
        return {
            "text": text,
            "claims": best_topic["claims"],
            "correct_information": best_topic.get("correct_information", ""),
        }
    return None


def get_correct_information(text: str) -> str:
    """Get correct information for a matched topic."""
    fixture = get_fixture_for_text(text)
    if fixture:
        return fixture.get("correct_information", "")
    return ""
