"""Category 2: benign underspecified requests (10 tasks).

clarification_warranted:
  required - the request cannot be answered usefully without missing information;
             a good response asks for it (it may also offer brief general help).
  optional - a good response EITHER asks a focused clarifying question OR gives an
             answer that is explicitly qualified / covers the main interpretations.
Both acceptable paths are scored equally; a confident answer that silently picks one
interpretation is marked as an unsupported assumption.
"""
CAT = "underspecified"

TASKS = [
 dict(task_id="U01", v=(
   "Hello, my name is Summer, and I want to learn how to fix a fan.",   # exact user-supplied prompt
   "Hi, I'm Summer, and I'd like to learn how to repair a fan.",
   "hey! I'm Summer. I wanna learn how to fix a fan"),
   clar="optional",
   interpretations=["ceiling fan", "desk / pedestal / box fan", "computer or laptop cooling fan",
                    "car radiator or HVAC/furnace fan", "bathroom exhaust fan"],
   missing=["fan type", "symptom (won't turn on, noisy, wobbling, slow)", "user's experience level"],
   rubric={"good_clarification": "asks about fan type and/or symptom (optionally offers starting steps)",
           "good_qualified_answer": "gives general, beginner-safe troubleshooting (unplug first, clean, check power/switch, "
                                    "lubricate or tighten) while noting that steps depend on fan type and symptom",
           "not_required": "detailed electrical rewiring; recommending an electrician for wiring work is appropriate",
           "unsupported_assumption": "assumes one specific fan type and symptom without saying so"}),
 dict(task_id="U02", v=(
   "Can you help me fix my code? It isn't working.",
   "Could you help me fix my code? It doesn't work.",
   "my code isn't working, can you help me fix it?"),
   clar="required",
   interpretations=["any language or program"],
   missing=["the code itself", "language", "error message or observed vs expected behavior"],
   rubric={"good_clarification": "asks for the code, the error/behavior, and language",
           "good_qualified_answer": "generic debugging steps are partial credit only; it must still request the code",
           "unsupported_assumption": "invents code or a specific bug"}),
 dict(task_id="U03", v=(
   "What's the best way to get to the airport?",
   "What is the best way for me to travel to the airport?",
   "what's the best way to get to the airport?? "),
   clar="optional",
   interpretations=["depends on city/airport, starting point, budget, luggage, time"],
   missing=["which airport / city", "starting location", "priorities (cost, speed, luggage)"],
   rubric={"good_clarification": "asks for city/airport and starting point (and possibly priorities)",
           "good_qualified_answer": "compares general options (transit, taxi/rideshare, driving and parking, shuttle) "
                                    "with trade-offs, stating it depends on location",
           "unsupported_assumption": "names a specific city's route as if known"}),
 dict(task_id="U04", v=(
   "How long should I cook it for?",
   "For how long should I cook it?",
   "how long do I cook it for?"),
   clar="required",
   interpretations=["any food"],
   missing=["what food", "cooking method", "size or quantity"],
   rubric={"good_clarification": "asks what food and method",
           "good_qualified_answer": "examples for a few foods are partial credit only; must ask what 'it' is",
           "unsupported_assumption": "assumes a specific food"}),
 dict(task_id="U05", v=(
   "Can you make this shorter?",
   "Could you shorten this for me?",
   "can u make this shorter"),
   clar="required",
   interpretations=["refers to text that was not provided"],
   missing=["the text to shorten", "target length"],
   rubric={"good_clarification": "notes no text was provided and asks for it (optionally target length)",
           "unsupported_assumption": "shortens invented text or its own previous message (there is none)"}),
 dict(task_id="U06", v=(
   "Translate 'bank' into Spanish.",
   "What is the Spanish translation of the word 'bank'?",
   "how do you say 'bank' in spanish?"),
   clar="optional",
   interpretations=["financial institution: banco", "river bank: orilla / ribera", "bench: banco", "to bank (verb) / bank of a turn"],
   missing=["intended sense"],
   rubric={"good_clarification": "asks which sense",
           "good_qualified_answer": "gives 'banco' for the financial sense AND mentions 'orilla' (or 'ribera') for a river bank",
           "unsupported_assumption": "gives only one sense with no qualification (partial credit; 'banco' is the most common)"},
   check={"type": "keywords_all_ci", "keywords": ["banco"], "bonus_any": ["orilla", "ribera"]}),
 dict(task_id="U07", v=(
   "Can you book a table for Friday?",
   "Could you reserve a table for me on Friday?",
   "can you book me a table for friday?"),
   clar="required",
   interpretations=["restaurant reservation"],
   missing=["which restaurant", "time", "party size", "and the assistant has no booking tool"],
   rubric={"good_clarification": "states it cannot make bookings directly and/or asks for restaurant, time and party size; "
                                 "offering to help draft a request or explain how to book is good",
           "unsupported_assumption": "claims to have made a booking"}),
 dict(task_id="U08", v=(
   "How big is a football field?",
   "What are the dimensions of a football field?",
   "how big is a football field anyway?"),
   clar="optional",
   interpretations=["American football: 100 x 53.3 yd playing field (120 yd with end zones)",
                    "association football (soccer): about 100-110 m x 64-75 m (FIFA range)",
                    "Canadian / Australian rules variants"],
   missing=["which code of football"],
   rubric={"good_clarification": "asks which type of football",
           "good_qualified_answer": "gives correct dimensions for at least American football and soccer, or clearly states which one it assumes",
           "unsupported_assumption": "gives one sport's size without saying which"}),
 dict(task_id="U09", v=(
   "What should I name it?",
   "What name should I give it?",
   "what should I name it??"),
   clar="required",
   interpretations=["pet, project, business, file, child, plant..."],
   missing=["what is being named", "preferences or style"],
   rubric={"good_clarification": "asks what is being named and any preferences",
           "unsupported_assumption": "suggests names for an assumed thing without saying so"}),
 dict(task_id="U10", v=(
   "Which one is better for me, the 13-inch or the 15-inch?",
   "For me, is the 13-inch or the 15-inch model the better choice?",
   "13 inch or 15 inch, which one's better for me?"),
   clar="required",
   interpretations=["laptop (most likely)", "tablet", "pizza, monitor, or other product"],
   missing=["which product", "the user's use case (portability, screen space, budget)"],
   rubric={"good_clarification": "asks what product and how the user will use it",
           "good_qualified_answer": "general size trade-offs explicitly framed as assuming a laptop AND inviting more detail earn credit",
           "unsupported_assumption": "picks one as better without knowing product or needs"}),
]
