"""Pre-loaded sample documents for the demo + mock-mode fixtures."""
from __future__ import annotations

SAMPLE_1_HISTORY = (
    "The French Revolution began in 1789 when King Louis XVI called an emergency meeting of "
    "the Estates-General to address the financial crisis. The storming of the Bastille on "
    "July 14, 1789 marked a turning point, as it freed 723 political prisoners who had been "
    "held there for decades. Marie Antoinette famously said \"Let them eat cake\" in response "
    "to news of the bread shortages, a quote that became synonymous with royal indifference. "
    "Napoleon Bonaparte later rose to power and was crowned Emperor in Notre Dame Cathedral "
    "in 1804, with Pope Pius VII presiding over the ceremony. The revolution ultimately led "
    "to the Declaration of the Rights of Man, drafted primarily by Thomas Jefferson during "
    "his time in Paris as US ambassador."
)

SAMPLE_2_MEDICAL = (
    "Aspirin (acetylsalicylic acid) was first synthesized by Felix Hoffmann at Bayer in 1897 "
    "and has since become one of the most widely used medications worldwide. Clinical studies "
    "have shown that a daily low-dose aspirin of 81mg reduces the risk of heart attack by "
    "approximately 44% in adults over 50. The WHO classifies aspirin as an essential medicine "
    "for cardiovascular disease prevention globally. Recent research published in the New "
    "England Journal of Medicine in 2019 found that aspirin also demonstrates significant "
    "efficacy against colorectal cancer, reducing incidence by 31% in a cohort of 12,000 "
    "patients followed over 8 years. The recommended daily dose for pain relief is 500-1000mg, "
    "with no more than 4000mg per day."
)

SAMPLE_3_RESEARCH = (
    "The James Webb Space Telescope (JWST) launched on December 25, 2021, from the Guiana "
    "Space Centre aboard an Ariane 5 rocket. It is a joint project of NASA, the European "
    "Space Agency, and the Canadian Space Agency. JWST orbits the Sun near the Earth-Sun L2 "
    "Lagrange point, approximately 1.5 million kilometers from Earth. Its primary mirror is "
    "composed of 18 hexagonal gold-coated beryllium segments, totaling 6.5 meters in "
    "diameter. The telescope observes primarily in the near- and mid-infrared spectrum, "
    "which enables it to see through cosmic dust and observe the earliest galaxies in the "
    "universe."
)

SAMPLES = [
    {
        "id": "sample1",
        "title": "AI-written history article (contains hallucinations)",
        "description": "A short summary of the French Revolution with several planted factual errors.",
        "text": SAMPLE_1_HISTORY,
    },
    {
        "id": "sample2",
        "title": "AI medical brief (contains high-stakes errors)",
        "description": "Aspirin clinical overview — some real facts, some fabricated statistics & citations.",
        "text": SAMPLE_2_MEDICAL,
    },
    {
        "id": "sample3",
        "title": "AI research summary (mostly accurate)",
        "description": "A short, mostly-correct summary of the James Webb Space Telescope.",
        "text": SAMPLE_3_RESEARCH,
    },
]


def get_sample(sample_id: str):
    for s in SAMPLES:
        if s["id"] == sample_id:
            return s
    return None
