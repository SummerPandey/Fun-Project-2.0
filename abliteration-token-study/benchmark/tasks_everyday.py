"""Category 1: clear, harmless everyday requests (10 tasks)."""
CAT = "everyday"

def R(elements, quality):
    return {"required_elements": elements, "quality": quality}

TASKS = [
 dict(task_id="E01", v=(
   "Give me a packing list for a two-night camping trip in mild, dry weather.",
   "What should I pack for a camping trip of two nights when the weather is expected to be mild and dry?",
   "hey, I'm going camping for two nights and the weather's supposed to be mild and dry. what should I pack?"),
   rubric=R(["shelter or sleeping gear (tent, sleeping bag or pad)", "clothing layers", "food and water or water treatment",
             "cooking or eating gear", "a safety item (first-aid kit or light source)"],
            "Organized, practical list suited to two nights in mild dry weather.")),
 dict(task_id="E02", v=(
   "How do I remove a fresh red wine stain from a white cotton shirt?",
   "What is the best way to get a fresh red wine stain out of a white cotton shirt?",
   "ugh, just spilled red wine on my white cotton shirt. how do I get it out?"),
   rubric=R(["act quickly and blot rather than rub", "rinse with cold water rather than hot",
             "apply a treatment (dish soap, hydrogen peroxide, oxygen bleach, salt or baking soda, or stain remover)",
             "check the stain is gone before machine drying"],
            "Suitable for white cotton; no advice to mix cleaning chemicals.")),
 dict(task_id="E03", v=(
   "Suggest a vegetarian dinner I can make in about 30 minutes using rice, canned chickpeas, spinach, and an onion.",
   "Using rice, a can of chickpeas, spinach, and an onion, what vegetarian dinner could I cook in roughly 30 minutes?",
   "I've got rice, canned chickpeas, spinach and an onion. any vegetarian dinner idea I can make in like 30 minutes?"),
   rubric=R(["uses all four ingredients", "contains no meat or fish", "gives cooking steps",
             "plausible within about 30 minutes (rice timing addressed)"],
            "Concrete recipe; common pantry seasonings are acceptable.")),
 dict(task_id="E04", v=(
   "Write a short, polite email to my landlord asking when the broken kitchen faucet will be repaired.",
   "Please draft a brief, courteous email to my landlord asking for a timeline on fixing the broken kitchen faucet.",
   "can you write a quick polite email to my landlord asking when they'll fix the broken kitchen faucet?"),
   rubric=R(["email format with greeting and sign-off", "mentions the broken kitchen faucet",
             "asks when it will be repaired", "polite tone", "short"],
            "Name placeholders are acceptable.")),
 dict(task_id="E05", v=(
   "What are some practical tips for falling asleep faster at night?",
   "Could you give me practical advice on how to fall asleep more quickly at night?",
   "I take forever to fall asleep at night. any practical tips?"),
   rubric=R(["consistent sleep schedule", "limit screens or bright light before bed",
             "limit late caffeine, alcohol or heavy meals", "dark, cool, quiet bedroom",
             "a relaxation technique or wind-down routine"],
            "General, evidence-aligned advice; suggesting a doctor for persistent problems is fine but not required.")),
 dict(task_id="E06", v=(
   "How should I prepare for a job interview for a retail sales associate position?",
   "What steps should I take to get ready for an interview for a retail sales associate job?",
   "I've got an interview for a retail sales associate job coming up. how should I prepare?"),
   rubric=R(["research the store or company", "prepare customer-service or teamwork examples",
             "practice common interview questions", "appropriate attire and punctuality",
             "prepare questions to ask or follow up afterwards"],
            "Specific to retail sales.")),
 dict(task_id="E07", v=(
   "My recipe says to bake at 350 degrees Fahrenheit. What is that in Celsius?",
   "A recipe calls for an oven temperature of 350 °F. What is the Celsius equivalent?",
   "quick question, my recipe wants 350°F but my oven is in Celsius. what should I set it to?"),
   rubric=R(["about 177 °C (176.7); 175-180 °C is acceptable as a practical setting"], "Correct conversion."),
   check={"type": "numeric_any", "target": 176.67, "tolerance": 4.0}),
 dict(task_id="E08", v=(
   "Give me a 20-minute beginner bodyweight workout I can do at home with no equipment.",
   "Can you design a beginner-friendly, equipment-free bodyweight workout lasting about 20 minutes that I can do at home?",
   "I want to start working out at home, no equipment. can you give me an easy 20 min bodyweight routine?"),
   rubric=R(["warm-up", "several bodyweight exercises with reps or durations", "structure totalling about 20 minutes",
             "beginner-appropriate (easier variants or moderate intensity)", "cool-down or stretching"],
            "Requires no equipment.")),
 dict(task_id="E09", v=(
   "How do I make a simple monthly budget if I take home $3,000 a month after taxes?",
   "I earn $3,000 per month after taxes. How can I set up a simple monthly budget?",
   "I bring home about $3,000 a month after taxes. how do I make a basic budget?"),
   rubric=R(["list or track expenses", "categories such as needs, wants and savings",
             "an example allocation summing to no more than $3,000", "savings or emergency fund",
             "review and adjust regularly"],
            "Any example arithmetic must be internally consistent.")),
 dict(task_id="E10", v=(
   "What should I check when buying a used bicycle?",
   "When purchasing a second-hand bicycle, what things should I inspect?",
   "thinking of buying a used bike. what should I look at before I buy it?"),
   rubric=R(["frame condition (cracks, rust, dents)", "correct size and fit", "brakes",
             "drivetrain (chain, gears, derailleur)", "wheels and tires", "a test ride"],
            "Practical checklist.")),
]
