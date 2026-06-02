from __future__ import annotations

import re


def apply_curated_corrections(text: str) -> str:
    """Apply user-verified corrections to known source text defects."""
    text = text.replace(
        "महायज्ञः Mahayajña\nThe great sacrificer.\n\nमहांश्चासौ यज्वश्चेति लोकसङ्ग्रहार्थं यज्ञान् निर्वर्तवन् महायज्ञः ।",
        "महायज्वा Mahāyajvā\nThe great sacrificer.\n\nमहांश्चासौ यज्वश्चेति लोकसङ्ग्रहार्थं यज्ञान् निर्वर्तवन् महायज्वा ।",
        1,
    )
    text = text.replace(
        "Thus, He is Mahayajña,\nthe great sacrificer.",
        "Thus, He is Mahāyajvā,\nthe great sacrificer.",
        1,
    )
    text = text.replace(
        "lokasaṅgraha, the good of the world and hence, He is\nMahayajña.\n\nमहायज्ञः Mahayajña",
        "lokasaṅgraha, the good of the world and hence, He is\nMahāyajvā.\n\nमहायज्ञः Mahayajña",
        1,
    )
    text = text.replace(
        "HATTA: Kṛtagamaḥ (655)\nThe author of the Vedas.",
        "कृतागमः Kṛtagamaḥ (655)\nThe author of the Vedas.",
        1,
    )
    text = text.replace(
        "अनन्त: Anantaḥ (886)\nThe limitless.",
        "अनन्तः Anantaḥ (886)\nThe limitless.",
        1,
    )
    text = text.replace(
        "Dhananjayaḥ Dhananjayah\nThe conqueror of wealth.",
        "धनञ्जयः Dhananjayah\nThe conqueror of wealth.",
        1,
    )
    text = text.replace(
        "WY: Prabhuḥ (299)\nThe one who has unsurpassed skill.",
        "प्रभुः Prabhuḥ (299)\nThe one who has unsurpassed skill.",
        1,
    )
    text = text.replace(
        "Ajah Ajah (204, 521)\nThe unborn.",
        "अजः Ajah (204, 521)\nThe unborn.",
        1,
    )
    text = text.replace(
        "Aja: Sarveśvaraḥ\nThe Lord of all.",
        "सर्वेश्वरः Sarveśvaraḥ\nThe Lord of all.",
        1,
    )
    text = text.replace(
        "Ajaḥ (95, 521)\n-The one who moves.",
        "अजः Ajaḥ (95, 521)\nThe one who moves.",
        1,
    )
    text = text.replace(
        "HAM: Anala (711)\nThe one who is never satiated.",
        "अनलः Anala (711)\nThe one who is never satiated.",
        1,
    )
    text = text.replace(
        "Kāmaha: Kāmaha\nThe destroyer of desires.",
        "कामहा Kāmaha\nThe destroyer of desires.",
        1,
    )
    text = text.replace(
        "Yadḥ Suvrataḥ (818)\nThe one with an admirable commitment.",
        "सुव्रतः Suvrataḥ (818)\nThe one with an admirable commitment.",
        1,
    )
    text = text.replace(
        "सु, शोभनं व्रतमस्येति Yadḥ |",
        "सु, शोभनं व्रतमस्येति सुव्रतः |",
        1,
    )
    text = text.replace(
        "Ajaḥ Ajah (95, 204)\nThe one in the form of Manmatha.",
        "अजः Ajah (95, 204)\nThe one in the form of Manmatha.",
        1,
    )
    text = text.replace(
        "Mahārhaḥ Maharhaḥ\nThe one who deserves worship.",
        "महार्हः Maharhaḥ\nThe one who deserves worship.",
        1,
    )
    text = text.replace(
        "HAG: Analaḥ (293)\nThe one who has no limit.",
        "अनलः Analaḥ (293)\nThe one who has no limit.",
        1,
    )
    text = text.replace(
        "Ad: Suvrataḥ (455)\nThe one who accepts all the offerings.",
        "सुव्रतः Suvrataḥ (455)\nThe one who accepts all the offerings.",
        1,
    )
    text = text.replace(
        "AST Srasta (588)\nThe creator of all.",
        "स्रष्टा Srasta (588)\nThe creator of all.",
        1,
    )
    text = text.replace(
        "अनिदेश्यवपुः Anirdesyavapuh (656)",
        "अनिर्देश्यवपुः Anirdesyavapuh (656)",
        1,
    )
    text = text.replace(
        "तत् अनिदेश्यं\nवपुरस्येति अनिर्देश्यवपु:।",
        "तत् अनिर्देश्यं\nवपुरस्येति अनिर्देश्यवपु:।",
        1,
    )
    text = text.replace(
        "अनिदेश्यवपुविष्णुवीरोऽ नन्तो धनञ्जयः ।। ७० ।।",
        "अनिर्देश्यवपुविष्णुवीरोऽ नन्तो धनञ्जयः ।। ७० ।।",
        1,
    )
    text = text.replace(
        "तदेव रूपमस्येति\nअनिदेश्यवपुः।",
        "तदेव रूपमस्येति\nअनिर्देश्यवपुः।",
        1,
    )
    text = text.replace(
        "सुवर्णबिन्दुरक्षोभ्यः सर्ववागीश्चरेश्वरः।\n\n"
        "महाहदो Herta महाभूतो महानिधिः।। ८६।।\n"
        "mahāhardo mahāgarbho mahābhūto mahānidhiḥ । । 86\n\n"
        "suvarnabinduraksobhyah sarvavagisvaresvarah |\n"
        "mahāhardo mahāgarbho mahābhūto mahānidhiḥ । । 86",
        "सुवर्णबिन्दुरक्षोभ्यः सर्ववागीश्वरेश्वरः।\n"
        "महाह्रदो महागर्तो महाभूतो महानिधिः।। ८६।।\n\n"
        "suvarnabinduraksobhyah sarvavagisvaresvarah |\n"
        "mahāhrado mahāgarto mahābhūto mahānidhiḥ || 86",
        1,
    )
    text = text.replace(
        "सर्ववागीश्वरोत्තරः Sarvavagisveśvarah\nThe Lord of all the lords of speech.",
        "सर्ववागीश्वरेश्वरः Sarvavagisveśvarah\nThe Lord of all the lords of speech.",
        1,
    )
    text = text.replace(
        "सर्वाणां वागीश्वराणां ब्रह्मादीनांपि ईश्वर: सर्ववागीश्वरोत्තරः।",
        "सर्वाणां वागीश्वराणां ब्रह्मादीनांपि ईश्वर: सर्ववागीश्वरेश्वरः।",
        1,
    )
    text = text.replace(
        "Hert: Mahāgartaḥ\nThe one who is like a great canyon.",
        "महागर्तः Mahāgartaḥ\nThe one who is like a great canyon.",
        1,
    )
    text = text.replace(
        "महागर्तवद् अस्य माया महती दुरत्यया इति Hert: |",
        "महागर्तवद् अस्य माया महती दुरत्यया इति महागर्तः |",
        1,
    )
    text = text.replace(
        "Held: Mahābhūtaḥ\nThe great being.",
        "महाभूतः Mahābhūtaḥ\nThe great being.",
        1,
    )
    text = text.replace(
        "महांश्चासौ निधिश्च इति महानिdeoः।",
        "महांश्चासौ निधिश्च इति महानिधिः।",
        1,
    )
    text = text.replace(
        "अनादिनिधनो धाता विधाता धातुरुत्paramः।। ५ ।।",
        "अनादिनिधनो धाता विधाता धातुरुत्तमः।। ५ ।।",
        1,
    )
    text = text.replace(
        "वेधाः स्वाङ्गोऽजितः कृष्णो दृढः सङ्कर्षणोऽचytah |",
        "वेधाः स्वाङ्गोऽजितः कृष्णो दृढः सङ्कर्षणोऽच्युतः |",
        1,
    )
    text = text.replace(
        "bhagavan bhagaha’ऽnandi vanamali halayudhah |",
        "bhagavan bhagaha’nandi vanamali halayudhah |",
        1,
    )
    text = text.replace(
        "आश्चaryaवच्चैनमन्यः शृणोति श्रुत्वाप्येनं वेद न चैव कश्चित्।। 5.2.29",
        "आश्चर्यवच्चैनमन्यः शृणोति श्रुत्वाप्येनं वेद न चैव कश्चित्।। 5.2.29",
        1,
    )
    text = text.replace(
        "सर्वप्रhinayudha ओं नम इति।।",
        "सर्वप्रहरणायुध ओं नम इति।।",
        1,
    )
    text = text.replace(
        "धनुर्धरो धनुवदो दण्डो दमयिता दमः।\n\n"
        "अपराजितः सर्वसहो नियन्ताऽनियमोऽयमः।। ९२।।\n"
        "dhanurdharo dhanuvado daṇḍo damayitā damaḥ |\n"
        "aparajitah sarvasaho niyantā’niyamo’yamah | | 92",
        "धनुर्धरो धनुर्वेदो दण्डो दमयिता दमः।\n"
        "अपराजितः सर्वसहो नियन्ताऽनियमोऽयमः।। ९२।।\n\n"
        "dhanurdharo dhanurvedo daṇḍo damayitā damaḥ |\n"
        "aparajitah sarvasaho niyantā’niyamo’yamah || 92",
        1,
    )
    text = text.replace("योगं विदन्ति विचारयet, जानन्ति, उक्त इति वा योगविदः।", "योगं विदन्ति विचारयन्ति, जानन्ति, उक्त इति वा योगविदः।", 1)
    text = text.replace("शं सुखं भक्तानां (मङ्गलं मोce) भावयतीति शंभुः ।", "शं सुखं भक्तानां (मङ्गलं मोक्षं) भावयतीति शंभुः ।", 1)
    text = text.replace("मेधा - बहुग्रन्थ-धारण-सामarkyam, सा यस्यास्ति स मेधावी ।", "मेधा - बहुग्रन्थ-धारण-सामर्थ्यम्, सा यस्यास्ति स मेधावी ।", 1)
    text = text.replace("संसारचक्रम् आवर्तयितुं शक्Num अस्येति आवर्तनः।", "संसारचक्रम् आवर्तयितुं शक्तिः अस्येति आवर्तनः।", 1)
    text = text.replace("ओजस्तेजोद्यutidhar Ojastejodyutidharah", "ओजस्तेजोद्युतिधरः Ojastejodyutidharah", 1)
    text = text.replace("ज्ञानं उत्तमं प्रकृष्टमजन्यं अनवच्छिन्नं, सर्वस्य साधकतममिति ज्ञानमुत्thamं ब्रह्म।", "ज्ञानं उत्तमं प्रकृष्टमजन्यं अनवच्छिन्नं, सर्वस्य साधकतममिति ज्ञानमुत्तमं ब्रह्म।", 1)
    text = text.replace("कूटस्थः SARA |", "कूटस्थः अक्षरम् |", 1)
    text = text.replace("विश्वरूपत्वात्पुरुः, उत्कृष्टत्वात्सत्तमः। पुरुश्नासौ सत्तमश्चेति पुरुसत्lamः |", "विश्वरूपत्वात्पुरुः, उत्कृष्टत्वात्सत्तमः। पुरुश्नासौ सत्तमश्चेति पुरुसत्तमः |", 1)
    text = text.replace("सत्या सन्धा सङ्कल्पः अस्येति AAAS: |", "सत्या सन्धा सङ्कल्पः अस्येति सत्यसन्धः |", 1)
    text = text.replace("सर्वभूतेभ्यः समुद्रिक्तत्वात् उदीfnः।", "सर्वभूतेभ्यः समुद्रिक्तत्वात् उदीर्णः।", 1)
    text = text.replace("यमुनासम्बन्निना देवकीवसुदेव नन्द यशोदा बलबhadra सुभद्रादयः", "यमुनासम्बन्निना देवकीवसुदेव नन्द यशोदा बलभद्र सुभद्रादयः", 1)
    text = text.replace("तस्मात् TSES: |", "तस्मात् दुर्धरः |", 1)
    text = text.replace("इन्द्रस्य कर्मव कर्मास्येति इdtraकर्मा।", "इन्द्रस्य कर्मव कर्मास्येति इन्द्रकर्मा।", 1)
    text = text.replace("पर्jan़यवद् आध्यात्मिकादितापत्रयं शमयतीति", "पर्जन्यवद् आध्यात्मिकादितापत्रयं शमयतीति", 1)
    text = text.replace("आश्चर्यो वक्ता कुशलोऽस्य SAT आश्चर्यो ज्ञाता कुशलानुशिष्ट:", "आश्चर्यो वक्ता कुशलोऽस्य लब्धा आश्चर्यो ज्ञाता कुशलानुशिष्ट:", 1)
    text = text.replace("यज्ञगुphan |", "यज्ञगुह्यम् |", 1)
    text = text.replace(
        "अवितः Arcitaḥ\nThe one who is worshipped.",
        "अर्चितः Arcitaḥ\nThe one who is worshipped.",
        1,
    )
    text = text.replace(
        "सर्वदेवैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विद्यैर्विdyaiḥ…\n(Note: The OCR for the Sanskrit line is heavily corrupted; however, based on the context of “Arcita” and “worshipped by all”, the intended meaning is “worshipped by all devas/vidyas”.)",
        "सर्वदेवैर्विद्यैश्च अर्चित इति अर्चितः।",
        1,
    )
    text = re.sub(
        r"सर्वदेवैर्विद्यैर्विद्यै.*?\(Note: The OCR for the Sanskrit line is heavily corrupted; however, based on the context of “Arcita” and “worshipped by all”, the intended meaning is “worshipped by all devas/vidyas”.\)",
        "सर्वदेवैर्विद्यैश्च अर्चित इति अर्चितः।",
        text,
        count=1,
        flags=re.DOTALL,
    )
    return text
