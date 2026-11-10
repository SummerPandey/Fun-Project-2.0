"""Category 5: explanation, summarization and instruction following (10 tasks).
Explicit constraints are checked deterministically; content quality goes to the judge."""
CAT = "instruction"

LIB = ("The town of Millbrook opened its new public library on March 3. The building cost $4.2 million, "
       "funded mostly by a state grant, and replaces a branch that had been closed since a 2019 flood. "
       "It has a children's wing, twelve study rooms, and a makerspace with two 3D printers. "
       "Head librarian Dana Ortiz said visitors in the first week exceeded 5,000. "
       "The library is open seven days a week, from 9 a.m. to 8 p.m.")
GARDEN = ("Volunteers at the Eastside Community Garden harvested 1,200 pounds of vegetables this season, "
          "a 30 percent increase over last year. Most of the produce, mainly tomatoes, squash and beans, was donated "
          "to two local food pantries. The garden added a rainwater collection system in April, which cut its "
          "water bill by about half. Organizers plan to add ten more raised beds next spring and are seeking "
          "volunteers for weekend shifts.")

TASKS = [
 dict(task_id="I01", v=(
   "List exactly three benefits of regular walking as a numbered list, with no other text.",
   "Give exactly three benefits of walking regularly, formatted as a numbered list and with no additional text.",
   "give me exactly 3 benefits of walking regularly — numbered list only, nothing else."),
   check={"type": "numbered_list_exact", "n": 3},
   rubric={"required_elements": ["three distinct, accurate benefits"], "quality": "No intro or outro text."}),
 dict(task_id="I02", v=(
   "Write a haiku about autumn rain. Output only the three lines of the haiku.",
   "Compose a haiku on the subject of autumn rain, and output nothing but its three lines.",
   "write me a haiku about autumn rain — just the three lines, nothing else."),
   check={"type": "line_count_exact", "n": 3},
   rubric={"required_elements": ["about autumn rain", "roughly 5-7-5 syllables"], "quality": "Only the poem."}),
 dict(task_id="I03", v=(
   f"Summarize the following paragraph in one sentence of no more than 25 words.\n\n{LIB}",
   f"In a single sentence of 25 words or fewer, summarize this paragraph.\n\n{LIB}",
   f"can you sum this up in one sentence, 25 words max?\n\n{LIB}"),
   check={"type": "summary", "max_words": 25, "max_sentences": 1,
          "required_facts": [["millbrook"], ["library"], ["open", "opened"]],
          "bonus_facts": [["4.2", "million"], ["flood"], ["5,000", "5000"]]},
   rubric={"required_elements": ["Millbrook opened a new library", "at least one key detail (cost/grant, flood replacement, features, visitors)"],
           "unsupported": "any fact not in the paragraph"}),
 dict(task_id="I04", v=(
   "Explain what photosynthesis is to a 10-year-old in fewer than 80 words.",
   "In under 80 words, explain photosynthesis so that a ten-year-old could understand it.",
   "explain photosynthesis to a 10 year old, under 80 words please."),
   check={"type": "word_limit_keywords", "max_words": 79,
          "keywords_any_groups": [["sun", "sunlight", "light"], ["water"], ["carbon dioxide", "air", "co2"], ["sugar", "food", "energy"], ["oxygen"]]},
   rubric={"required_elements": ["sunlight", "water", "carbon dioxide/air", "makes sugar/food", "releases oxygen"], "quality": "Child-appropriate language."}),
 dict(task_id="I05", v=(
   "Return a JSON object with the keys \"city\" and \"country\" for the capital of Japan. Output only the JSON.",
   "Output only a JSON object, with keys \"city\" and \"country\", describing the capital of Japan.",
   "give me just a JSON object with \"city\" and \"country\" keys for the capital of Japan, nothing else."),
   check={"type": "json_exact", "expected": {"city": "Tokyo", "country": "Japan"}},
   rubric={"required_elements": ["Tokyo", "Japan", "only JSON"]}),
 dict(task_id="I06", v=(
   f"Summarize the following passage in exactly three bullet points.\n\n{GARDEN}",
   f"Condense this passage into exactly three bullet points.\n\n{GARDEN}",
   f"can you boil this down to exactly 3 bullet points?\n\n{GARDEN}"),
   check={"type": "bullets_exact", "n": 3,
          "required_facts": [["1,200", "1200"], ["pantr", "donat"], ["rainwater", "rain water"]],
          "bonus_facts": [["30"], ["raised bed", "ten more", "10 more"], ["volunteer"]]},
   rubric={"required_elements": ["harvest amount/increase", "donation to food pantries", "rainwater system or future plans"],
           "unsupported": "any fact not in the passage"}),
 dict(task_id="I07", v=(
   "Write one sentence about the ocean that does not contain the letter 'e'. Output only the sentence.",
   "Output a single sentence about the ocean in which the letter 'e' never appears, and nothing else.",
   "write just one sentence about the ocean without using the letter e anywhere."),
   check={"type": "lipogram", "letter": "e"},   # topicality judged by the judge (most ocean words contain 'e')
   rubric={"required_elements": ["one sentence", "about the ocean", "no letter e"]}),
 dict(task_id="I08", v=(
   "Explain the difference between weather and climate in exactly two sentences.",
   "Using exactly two sentences, explain how weather differs from climate.",
   "what's the difference between weather and climate? answer in exactly two sentences."),
   check={"type": "sentence_count_exact", "n": 2, "keywords_all": ["weather", "climate"]},
   rubric={"required_elements": ["weather = short-term conditions", "climate = long-term average/patterns"]}),
 dict(task_id="I09", v=(
   "Give five words that rhyme with 'cat', in lowercase, separated by commas, and nothing else.",
   "List five words rhyming with 'cat', all lowercase and comma-separated, with no other text.",
   "give me 5 words that rhyme with cat — lowercase, separated by commas, nothing else."),
   check={"type": "rhyme_list", "n": 5, "suffixes": ["at", "att", "atte"], "exclude": ["cat"]},
   rubric={"required_elements": ["five distinct rhymes", "lowercase", "comma separated only"]}),
 dict(task_id="I10", v=(
   "Explain what a hash table is in under 120 words. Your answer must include the words 'key', 'bucket', and 'collision'.",
   "In fewer than 120 words, explain what a hash table is, making sure to use the words 'key', 'bucket', and 'collision'.",
   "explain what a hash table is, under 120 words, and make sure you use the words key, bucket and collision."),
   check={"type": "word_limit_keywords", "max_words": 119, "keywords_any_groups": [["key"], ["bucket"], ["collision"]]},
   rubric={"required_elements": ["hash function maps keys to buckets/indices", "collision handling", "fast average lookup"]}),
]
