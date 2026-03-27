"""
Belief Variance Experiment — Prompt Bank
=========================================
200 prompts stratified across 5 domains (40 each), designed to map LLM
belief topology across temperature settings.

Each prompt includes two alternate phrasings to separate semantic
uncertainty from phrasing sensitivity.
"""

from typing import TypedDict


class Prompt(TypedDict):
    id: str
    domain: str
    text: str
    alt_phrasings: list[str]


# ---------------------------------------------------------------------------
# Domain 1: factual_settled — Clear factual answers with strong consensus
# ---------------------------------------------------------------------------
FACTUAL_SETTLED: list[Prompt] = [
    {
        "id": "fs_001",
        "domain": "factual_settled",
        "text": "What is the capital of France?",
        "alt_phrasings": [
            "Which city serves as France's capital?",
            "Name the capital city of France.",
        ],
    },
    {
        "id": "fs_002",
        "domain": "factual_settled",
        "text": "What year did World War II end?",
        "alt_phrasings": [
            "In which year did WWII come to an end?",
            "When did the Second World War conclude?",
        ],
    },
    {
        "id": "fs_003",
        "domain": "factual_settled",
        "text": "What is the chemical formula for water?",
        "alt_phrasings": [
            "How is water represented in chemical notation?",
            "What molecule does H2O refer to?",
        ],
    },
    {
        "id": "fs_004",
        "domain": "factual_settled",
        "text": "How many continents are there on Earth?",
        "alt_phrasings": [
            "What is the total number of continents?",
            "How many major landmasses are classified as continents?",
        ],
    },
    {
        "id": "fs_005",
        "domain": "factual_settled",
        "text": "What planet is closest to the Sun?",
        "alt_phrasings": [
            "Which planet orbits nearest to the Sun?",
            "Name the innermost planet in our solar system.",
        ],
    },
    {
        "id": "fs_006",
        "domain": "factual_settled",
        "text": "What is the speed of light in a vacuum?",
        "alt_phrasings": [
            "How fast does light travel in a vacuum?",
            "What is the value of c in physics?",
        ],
    },
    {
        "id": "fs_007",
        "domain": "factual_settled",
        "text": "Who wrote Romeo and Juliet?",
        "alt_phrasings": [
            "Which playwright authored Romeo and Juliet?",
            "Romeo and Juliet was written by whom?",
        ],
    },
    {
        "id": "fs_008",
        "domain": "factual_settled",
        "text": "What is the boiling point of water at sea level in Celsius?",
        "alt_phrasings": [
            "At what temperature does water boil at standard atmospheric pressure?",
            "How many degrees Celsius is the boiling point of water at sea level?",
        ],
    },
    {
        "id": "fs_009",
        "domain": "factual_settled",
        "text": "What element does the symbol 'Au' represent?",
        "alt_phrasings": [
            "Which chemical element has the symbol Au?",
            "Au is the periodic table symbol for which element?",
        ],
    },
    {
        "id": "fs_010",
        "domain": "factual_settled",
        "text": "How many bones are in the adult human body?",
        "alt_phrasings": [
            "What is the total number of bones in a grown human?",
            "An adult human skeleton contains how many bones?",
        ],
    },
    {
        "id": "fs_011",
        "domain": "factual_settled",
        "text": "What is the largest organ in the human body?",
        "alt_phrasings": [
            "Which organ in the human body is the biggest?",
            "Name the human body's largest organ.",
        ],
    },
    {
        "id": "fs_012",
        "domain": "factual_settled",
        "text": "What language has the most native speakers worldwide?",
        "alt_phrasings": [
            "Which language is spoken natively by the most people?",
            "By native speaker count, what is the world's most spoken language?",
        ],
    },
    {
        "id": "fs_013",
        "domain": "factual_settled",
        "text": "What is the tallest mountain on Earth?",
        "alt_phrasings": [
            "Which mountain has the highest elevation above sea level?",
            "Name the world's tallest peak.",
        ],
    },
    {
        "id": "fs_014",
        "domain": "factual_settled",
        "text": "What is the square root of 144?",
        "alt_phrasings": [
            "Calculate the square root of 144.",
            "What number multiplied by itself gives 144?",
        ],
    },
    {
        "id": "fs_015",
        "domain": "factual_settled",
        "text": "What is the powerhouse of the cell?",
        "alt_phrasings": [
            "Which organelle is known as the cell's powerhouse?",
            "What cellular structure generates most of the cell's ATP?",
        ],
    },
    {
        "id": "fs_016",
        "domain": "factual_settled",
        "text": "Who was the first person to walk on the Moon?",
        "alt_phrasings": [
            "Which astronaut first set foot on the lunar surface?",
            "Name the first human to walk on the Moon.",
        ],
    },
    {
        "id": "fs_017",
        "domain": "factual_settled",
        "text": "What is the atomic number of carbon?",
        "alt_phrasings": [
            "How many protons does a carbon atom have?",
            "Carbon has what atomic number?",
        ],
    },
    {
        "id": "fs_018",
        "domain": "factual_settled",
        "text": "What is the longest river in the world?",
        "alt_phrasings": [
            "Which river has the greatest length on Earth?",
            "Name the world's longest river.",
        ],
    },
    {
        "id": "fs_019",
        "domain": "factual_settled",
        "text": "How many chromosomes do humans have?",
        "alt_phrasings": [
            "What is the chromosome count in human cells?",
            "Humans have how many chromosomes in a typical cell?",
        ],
    },
    {
        "id": "fs_020",
        "domain": "factual_settled",
        "text": "What gas do plants absorb during photosynthesis?",
        "alt_phrasings": [
            "Which gas is taken in by plants for photosynthesis?",
            "During photosynthesis, what gas do plants consume?",
        ],
    },
    {
        "id": "fs_021",
        "domain": "factual_settled",
        "text": "What is the freezing point of water in Fahrenheit?",
        "alt_phrasings": [
            "At what Fahrenheit temperature does water freeze?",
            "Water freezes at how many degrees Fahrenheit?",
        ],
    },
    {
        "id": "fs_022",
        "domain": "factual_settled",
        "text": "What is the most abundant element in the universe?",
        "alt_phrasings": [
            "Which element is most common in the universe?",
            "By mass, what element dominates the universe?",
        ],
    },
    {
        "id": "fs_023",
        "domain": "factual_settled",
        "text": "How many sides does a hexagon have?",
        "alt_phrasings": [
            "What is the number of sides on a hexagon?",
            "A hexagon is a polygon with how many edges?",
        ],
    },
    {
        "id": "fs_024",
        "domain": "factual_settled",
        "text": "What year was the Declaration of Independence signed?",
        "alt_phrasings": [
            "In what year did the signing of the Declaration of Independence occur?",
            "When was the US Declaration of Independence signed?",
        ],
    },
    {
        "id": "fs_025",
        "domain": "factual_settled",
        "text": "What is the smallest prime number?",
        "alt_phrasings": [
            "Which prime number is the lowest?",
            "Name the smallest number that is prime.",
        ],
    },
    {
        "id": "fs_026",
        "domain": "factual_settled",
        "text": "What is the main component of the Sun?",
        "alt_phrasings": [
            "What element makes up most of the Sun?",
            "The Sun is primarily composed of which element?",
        ],
    },
    {
        "id": "fs_027",
        "domain": "factual_settled",
        "text": "What is the currency of Japan?",
        "alt_phrasings": [
            "Which currency is used in Japan?",
            "Japan's official monetary unit is called what?",
        ],
    },
    {
        "id": "fs_028",
        "domain": "factual_settled",
        "text": "How many planets are in our solar system?",
        "alt_phrasings": [
            "What is the number of planets orbiting our Sun?",
            "Our solar system contains how many planets?",
        ],
    },
    {
        "id": "fs_029",
        "domain": "factual_settled",
        "text": "What does DNA stand for?",
        "alt_phrasings": [
            "What is the full name abbreviated as DNA?",
            "Spell out the acronym DNA.",
        ],
    },
    {
        "id": "fs_030",
        "domain": "factual_settled",
        "text": "Who painted the Mona Lisa?",
        "alt_phrasings": [
            "Which artist created the Mona Lisa?",
            "The Mona Lisa was painted by whom?",
        ],
    },
    {
        "id": "fs_031",
        "domain": "factual_settled",
        "text": "What is the largest ocean on Earth?",
        "alt_phrasings": [
            "Which ocean covers the most area?",
            "Name Earth's biggest ocean.",
        ],
    },
    {
        "id": "fs_032",
        "domain": "factual_settled",
        "text": "What force keeps us on the ground?",
        "alt_phrasings": [
            "Which fundamental force prevents us from floating away?",
            "What holds objects to the Earth's surface?",
        ],
    },
    {
        "id": "fs_033",
        "domain": "factual_settled",
        "text": "What is the chemical symbol for sodium?",
        "alt_phrasings": [
            "Which symbol represents sodium on the periodic table?",
            "Sodium is abbreviated as what in chemistry?",
        ],
    },
    {
        "id": "fs_034",
        "domain": "factual_settled",
        "text": "How many minutes are in one hour?",
        "alt_phrasings": [
            "One hour equals how many minutes?",
            "What is the number of minutes in an hour?",
        ],
    },
    {
        "id": "fs_035",
        "domain": "factual_settled",
        "text": "What is the hardest natural substance?",
        "alt_phrasings": [
            "Which naturally occurring substance is the hardest?",
            "Name the hardest material found in nature.",
        ],
    },
    {
        "id": "fs_036",
        "domain": "factual_settled",
        "text": "Who developed the theory of general relativity?",
        "alt_phrasings": [
            "Which physicist formulated general relativity?",
            "General relativity was proposed by whom?",
        ],
    },
    {
        "id": "fs_037",
        "domain": "factual_settled",
        "text": "What is the capital of Japan?",
        "alt_phrasings": [
            "Which city is Japan's capital?",
            "Name the capital city of Japan.",
        ],
    },
    {
        "id": "fs_038",
        "domain": "factual_settled",
        "text": "How many degrees are in a circle?",
        "alt_phrasings": [
            "A full circle contains how many degrees?",
            "What is the total degree measure of a circle?",
        ],
    },
    {
        "id": "fs_039",
        "domain": "factual_settled",
        "text": "What is the third planet from the Sun?",
        "alt_phrasings": [
            "Which planet is third in order from the Sun?",
            "Name the planet that orbits third from the Sun.",
        ],
    },
    {
        "id": "fs_040",
        "domain": "factual_settled",
        "text": "What is the value of pi to two decimal places?",
        "alt_phrasings": [
            "What are the first two decimal digits of pi?",
            "Express pi rounded to two decimals.",
        ],
    },
]

# ---------------------------------------------------------------------------
# Domain 2: factual_contested — Facts with genuine debate or ambiguity
# ---------------------------------------------------------------------------
FACTUAL_CONTESTED: list[Prompt] = [
    {
        "id": "fc_001",
        "domain": "factual_contested",
        "text": "Is Pluto a planet?",
        "alt_phrasings": [
            "Should Pluto be classified as a planet?",
            "Does Pluto count as a planet in our solar system?",
        ],
    },
    {
        "id": "fc_002",
        "domain": "factual_contested",
        "text": "Are eggs healthy to eat regularly?",
        "alt_phrasings": [
            "Is eating eggs every day good for your health?",
            "Do eggs have a net positive or negative effect on health?",
        ],
    },
    {
        "id": "fc_003",
        "domain": "factual_contested",
        "text": "Is coffee good for you?",
        "alt_phrasings": [
            "Does drinking coffee have net health benefits?",
            "Is regular coffee consumption healthy?",
        ],
    },
    {
        "id": "fc_004",
        "domain": "factual_contested",
        "text": "What is the healthiest diet for humans?",
        "alt_phrasings": [
            "Which dietary pattern is optimal for human health?",
            "What should the ideal human diet look like?",
        ],
    },
    {
        "id": "fc_005",
        "domain": "factual_contested",
        "text": "Is moderate alcohol consumption beneficial for health?",
        "alt_phrasings": [
            "Does drinking in moderation provide health benefits?",
            "Is a glass of wine a day actually good for you?",
        ],
    },
    {
        "id": "fc_006",
        "domain": "factual_contested",
        "text": "How many hours of sleep do adults need?",
        "alt_phrasings": [
            "What is the ideal amount of sleep for an adult?",
            "How much sleep should a grown person get each night?",
        ],
    },
    {
        "id": "fc_007",
        "domain": "factual_contested",
        "text": "Is saturated fat bad for your heart?",
        "alt_phrasings": [
            "Does eating saturated fat increase cardiovascular risk?",
            "Should people avoid saturated fats for heart health?",
        ],
    },
    {
        "id": "fc_008",
        "domain": "factual_contested",
        "text": "Did humans and dinosaurs ever coexist?",
        "alt_phrasings": [
            "Were humans alive at the same time as dinosaurs?",
            "Did any humans overlap in time with dinosaurs?",
        ],
    },
    {
        "id": "fc_009",
        "domain": "factual_contested",
        "text": "Is intelligence primarily genetic or environmental?",
        "alt_phrasings": [
            "What contributes more to intelligence: nature or nurture?",
            "Is IQ mostly determined by genes or upbringing?",
        ],
    },
    {
        "id": "fc_010",
        "domain": "factual_contested",
        "text": "How old is the universe?",
        "alt_phrasings": [
            "What is the estimated age of the universe?",
            "How many years has the universe existed?",
        ],
    },
    {
        "id": "fc_011",
        "domain": "factual_contested",
        "text": "Is nuclear energy safe?",
        "alt_phrasings": [
            "Can nuclear power be considered a safe energy source?",
            "Is nuclear power generation safe for communities?",
        ],
    },
    {
        "id": "fc_012",
        "domain": "factual_contested",
        "text": "Are GMO foods safe to eat?",
        "alt_phrasings": [
            "Is consuming genetically modified food harmful?",
            "Should people be concerned about eating GMOs?",
        ],
    },
    {
        "id": "fc_013",
        "domain": "factual_contested",
        "text": "Is there life elsewhere in the universe?",
        "alt_phrasings": [
            "Does extraterrestrial life exist?",
            "Are we alone in the universe?",
        ],
    },
    {
        "id": "fc_014",
        "domain": "factual_contested",
        "text": "What caused the extinction of the dinosaurs?",
        "alt_phrasings": [
            "Was the dinosaur extinction caused solely by an asteroid?",
            "What led to the mass extinction of dinosaurs?",
        ],
    },
    {
        "id": "fc_015",
        "domain": "factual_contested",
        "text": "Is the Shroud of Turin authentic?",
        "alt_phrasings": [
            "Was the Shroud of Turin really used to wrap Jesus?",
            "Is the Turin Shroud a genuine historical artifact?",
        ],
    },
    {
        "id": "fc_016",
        "domain": "factual_contested",
        "text": "Do humans use only 10% of their brain?",
        "alt_phrasings": [
            "Is the claim that we use only 10% of our brains true?",
            "How much of the brain do humans actually use?",
        ],
    },
    {
        "id": "fc_017",
        "domain": "factual_contested",
        "text": "Is fluoride in drinking water safe?",
        "alt_phrasings": [
            "Should communities add fluoride to their water supply?",
            "Does water fluoridation pose health risks?",
        ],
    },
    {
        "id": "fc_018",
        "domain": "factual_contested",
        "text": "Is organic food significantly healthier than conventional food?",
        "alt_phrasings": [
            "Are organic foods more nutritious than non-organic?",
            "Does choosing organic produce improve health outcomes?",
        ],
    },
    {
        "id": "fc_019",
        "domain": "factual_contested",
        "text": "Can animals be conscious?",
        "alt_phrasings": [
            "Do animals experience subjective consciousness?",
            "Are non-human animals sentient beings with awareness?",
        ],
    },
    {
        "id": "fc_020",
        "domain": "factual_contested",
        "text": "Is the gender pay gap primarily caused by discrimination?",
        "alt_phrasings": [
            "What is the main cause of the wage gap between men and women?",
            "Does workplace discrimination explain most of the gender pay gap?",
        ],
    },
    {
        "id": "fc_021",
        "domain": "factual_contested",
        "text": "Is breakfast the most important meal of the day?",
        "alt_phrasings": [
            "Does skipping breakfast harm your health?",
            "Is there scientific evidence that breakfast is essential?",
        ],
    },
    {
        "id": "fc_022",
        "domain": "factual_contested",
        "text": "Was the Library of Alexandria's destruction a major setback for human knowledge?",
        "alt_phrasings": [
            "Did the burning of the Library of Alexandria significantly delay human progress?",
            "How much knowledge was truly lost when the Library of Alexandria was destroyed?",
        ],
    },
    {
        "id": "fc_023",
        "domain": "factual_contested",
        "text": "Are standardized tests a good measure of intelligence?",
        "alt_phrasings": [
            "Do standardized test scores accurately reflect cognitive ability?",
            "Is IQ testing a valid measure of a person's intelligence?",
        ],
    },
    {
        "id": "fc_024",
        "domain": "factual_contested",
        "text": "Is string theory a scientifically valid theory?",
        "alt_phrasings": [
            "Should string theory be considered real science given its lack of testable predictions?",
            "Is string theory physics or mathematics?",
        ],
    },
    {
        "id": "fc_025",
        "domain": "factual_contested",
        "text": "Does sugar cause hyperactivity in children?",
        "alt_phrasings": [
            "Is there a link between sugar consumption and hyperactive behavior in kids?",
            "Do children actually get hyper from eating sugar?",
        ],
    },
    {
        "id": "fc_026",
        "domain": "factual_contested",
        "text": "Who built the Egyptian pyramids?",
        "alt_phrasings": [
            "Were the pyramids built by slaves or paid workers?",
            "What do we know about the laborers who constructed the pyramids at Giza?",
        ],
    },
    {
        "id": "fc_027",
        "domain": "factual_contested",
        "text": "Is multitasking effective?",
        "alt_phrasings": [
            "Can humans truly multitask, or do we just task-switch?",
            "Does trying to do multiple things at once reduce productivity?",
        ],
    },
    {
        "id": "fc_028",
        "domain": "factual_contested",
        "text": "Is the Sapir-Whorf hypothesis correct?",
        "alt_phrasings": [
            "Does the language you speak shape how you think?",
            "To what degree does language determine thought?",
        ],
    },
    {
        "id": "fc_029",
        "domain": "factual_contested",
        "text": "Is free will an illusion?",
        "alt_phrasings": [
            "Do humans have genuine free will?",
            "Does neuroscience show that free will doesn't exist?",
        ],
    },
    {
        "id": "fc_030",
        "domain": "factual_contested",
        "text": "Was Columbus the first European to reach the Americas?",
        "alt_phrasings": [
            "Did Vikings reach the Americas before Columbus?",
            "Who was truly the first European to arrive in the New World?",
        ],
    },
    {
        "id": "fc_031",
        "domain": "factual_contested",
        "text": "Is cold weather a cause of the common cold?",
        "alt_phrasings": [
            "Can being cold actually make you catch a cold?",
            "Does exposure to cold temperatures cause illness?",
        ],
    },
    {
        "id": "fc_032",
        "domain": "factual_contested",
        "text": "Is the Fermi paradox evidence against extraterrestrial civilizations?",
        "alt_phrasings": [
            "Does the lack of alien contact prove we're alone?",
            "What does the Fermi paradox tell us about life in the universe?",
        ],
    },
    {
        "id": "fc_033",
        "domain": "factual_contested",
        "text": "Are video games harmful to children's development?",
        "alt_phrasings": [
            "Do video games negatively affect kids' cognitive development?",
            "Is screen time from gaming bad for children?",
        ],
    },
    {
        "id": "fc_034",
        "domain": "factual_contested",
        "text": "Did the chicken or the egg come first?",
        "alt_phrasings": [
            "From an evolutionary perspective, which came first: the chicken or the egg?",
            "Is there a scientific answer to the chicken-and-egg question?",
        ],
    },
    {
        "id": "fc_035",
        "domain": "factual_contested",
        "text": "Is dark matter real or a flaw in our models?",
        "alt_phrasings": [
            "Does dark matter exist, or do we need modified gravity theories?",
            "Is the evidence for dark matter conclusive?",
        ],
    },
    {
        "id": "fc_036",
        "domain": "factual_contested",
        "text": "Can artificial intelligence become truly conscious?",
        "alt_phrasings": [
            "Is machine consciousness theoretically possible?",
            "Will AI ever have subjective experience?",
        ],
    },
    {
        "id": "fc_037",
        "domain": "factual_contested",
        "text": "Is the Turing test a good measure of machine intelligence?",
        "alt_phrasings": [
            "Does passing the Turing test prove a machine can think?",
            "Is the Turing test still a relevant benchmark for AI?",
        ],
    },
    {
        "id": "fc_038",
        "domain": "factual_contested",
        "text": "How much of human behavior is determined by genetics?",
        "alt_phrasings": [
            "What percentage of personality is genetic versus environmental?",
            "To what extent do genes dictate human behavior?",
        ],
    },
    {
        "id": "fc_039",
        "domain": "factual_contested",
        "text": "Is the obesity epidemic caused primarily by diet or lack of exercise?",
        "alt_phrasings": [
            "What contributes more to obesity: what we eat or how much we move?",
            "Can you exercise your way out of a bad diet?",
        ],
    },
    {
        "id": "fc_040",
        "domain": "factual_contested",
        "text": "Is meditation scientifically proven to improve mental health?",
        "alt_phrasings": [
            "Does the scientific evidence for meditation's benefits hold up to scrutiny?",
            "Are the claimed benefits of meditation supported by rigorous research?",
        ],
    },
]

# ---------------------------------------------------------------------------
# Domain 3: opinion_aesthetic — Subjective taste and preference questions
# ---------------------------------------------------------------------------
OPINION_AESTHETIC: list[Prompt] = [
    {
        "id": "oa_001",
        "domain": "opinion_aesthetic",
        "text": "Is jazz better than classical music?",
        "alt_phrasings": [
            "Which is superior: jazz or classical music?",
            "Would you rank jazz above classical as a musical genre?",
        ],
    },
    {
        "id": "oa_002",
        "domain": "opinion_aesthetic",
        "text": "What is the best color?",
        "alt_phrasings": [
            "Which color is the most aesthetically pleasing?",
            "If you had to pick one color as the best, what would it be?",
        ],
    },
    {
        "id": "oa_003",
        "domain": "opinion_aesthetic",
        "text": "Is modern art as valuable as Renaissance art?",
        "alt_phrasings": [
            "Does modern art have the same artistic merit as Renaissance masterpieces?",
            "Are contemporary art movements equal in quality to the Renaissance?",
        ],
    },
    {
        "id": "oa_004",
        "domain": "opinion_aesthetic",
        "text": "Are books better than movies?",
        "alt_phrasings": [
            "Is reading a novel superior to watching its film adaptation?",
            "Which provides a richer experience: books or films?",
        ],
    },
    {
        "id": "oa_005",
        "domain": "opinion_aesthetic",
        "text": "Is minimalism or maximalism a better design philosophy?",
        "alt_phrasings": [
            "Should design favor simplicity or complexity?",
            "Which produces better results: minimalist or maximalist design?",
        ],
    },
    {
        "id": "oa_006",
        "domain": "opinion_aesthetic",
        "text": "What is the most beautiful language in the world?",
        "alt_phrasings": [
            "Which language sounds the most aesthetically pleasing?",
            "If languages were ranked by beauty, which would be first?",
        ],
    },
    {
        "id": "oa_007",
        "domain": "opinion_aesthetic",
        "text": "Is photography a true art form?",
        "alt_phrasings": [
            "Does photography qualify as genuine art?",
            "Should photography be considered equal to painting as art?",
        ],
    },
    {
        "id": "oa_008",
        "domain": "opinion_aesthetic",
        "text": "What is the greatest novel ever written?",
        "alt_phrasings": [
            "Which book deserves the title of greatest novel of all time?",
            "If you could only name one novel as the best ever, what would it be?",
        ],
    },
    {
        "id": "oa_009",
        "domain": "opinion_aesthetic",
        "text": "Is autumn the most beautiful season?",
        "alt_phrasings": [
            "Which season is the most visually stunning?",
            "Would most people agree that fall is the prettiest season?",
        ],
    },
    {
        "id": "oa_010",
        "domain": "opinion_aesthetic",
        "text": "Are cats or dogs better pets?",
        "alt_phrasings": [
            "Which makes a better companion: a cat or a dog?",
            "If you could only have one, would you choose a cat or a dog?",
        ],
    },
    {
        "id": "oa_011",
        "domain": "opinion_aesthetic",
        "text": "Is black and white photography more artistic than color?",
        "alt_phrasings": [
            "Does removing color make a photograph more artistic?",
            "Are monochrome photos inherently more expressive than color ones?",
        ],
    },
    {
        "id": "oa_012",
        "domain": "opinion_aesthetic",
        "text": "What is the most overrated movie of all time?",
        "alt_phrasings": [
            "Which critically acclaimed film is actually not that good?",
            "Name a beloved movie that doesn't deserve its reputation.",
        ],
    },
    {
        "id": "oa_013",
        "domain": "opinion_aesthetic",
        "text": "Is Italian food the best cuisine in the world?",
        "alt_phrasings": [
            "Which national cuisine is the greatest?",
            "Does Italian food deserve the top spot among world cuisines?",
        ],
    },
    {
        "id": "oa_014",
        "domain": "opinion_aesthetic",
        "text": "Is the Beatles the greatest band of all time?",
        "alt_phrasings": [
            "Which band deserves the title of greatest ever?",
            "Were the Beatles really the best rock band in history?",
        ],
    },
    {
        "id": "oa_015",
        "domain": "opinion_aesthetic",
        "text": "Should buildings prioritize function over form?",
        "alt_phrasings": [
            "Is architectural beauty more important than practical function?",
            "In architecture, which matters more: aesthetics or utility?",
        ],
    },
    {
        "id": "oa_016",
        "domain": "opinion_aesthetic",
        "text": "Is abstract art real art?",
        "alt_phrasings": [
            "Does abstract art qualify as legitimate artistic expression?",
            "Should abstract paintings be considered true art?",
        ],
    },
    {
        "id": "oa_017",
        "domain": "opinion_aesthetic",
        "text": "Which is better: city life or country life?",
        "alt_phrasings": [
            "Is urban or rural living preferable?",
            "Would you choose to live in a big city or the countryside?",
        ],
    },
    {
        "id": "oa_018",
        "domain": "opinion_aesthetic",
        "text": "Is poetry a dying art form?",
        "alt_phrasings": [
            "Has poetry become irrelevant in the modern world?",
            "Is poetry still a meaningful form of expression?",
        ],
    },
    {
        "id": "oa_019",
        "domain": "opinion_aesthetic",
        "text": "What is the most impressive architectural wonder?",
        "alt_phrasings": [
            "Which building or structure is the greatest architectural achievement?",
            "Name the most awe-inspiring piece of architecture ever built.",
        ],
    },
    {
        "id": "oa_020",
        "domain": "opinion_aesthetic",
        "text": "Is a sunset more beautiful than a sunrise?",
        "alt_phrasings": [
            "Which is more visually striking: a sunset or a sunrise?",
            "Do sunsets or sunrises produce more beautiful skies?",
        ],
    },
    {
        "id": "oa_021",
        "domain": "opinion_aesthetic",
        "text": "Is vinyl better than digital music?",
        "alt_phrasings": [
            "Does vinyl produce better sound quality than digital formats?",
            "Is the warmth of analog records superior to digital clarity?",
        ],
    },
    {
        "id": "oa_022",
        "domain": "opinion_aesthetic",
        "text": "What is the most beautiful mathematical equation?",
        "alt_phrasings": [
            "Which equation in mathematics is the most elegant?",
            "Is Euler's identity truly the most beautiful equation?",
        ],
    },
    {
        "id": "oa_023",
        "domain": "opinion_aesthetic",
        "text": "Are tattoos a legitimate form of art?",
        "alt_phrasings": [
            "Should tattooing be considered a true art form?",
            "Do tattoos qualify as genuine artistic expression?",
        ],
    },
    {
        "id": "oa_024",
        "domain": "opinion_aesthetic",
        "text": "Is symmetry the foundation of beauty?",
        "alt_phrasings": [
            "Does beauty require symmetry?",
            "Is asymmetry ever more beautiful than symmetry?",
        ],
    },
    {
        "id": "oa_025",
        "domain": "opinion_aesthetic",
        "text": "What is the most beautiful natural landscape on Earth?",
        "alt_phrasings": [
            "Which natural scenery is the most breathtaking?",
            "Name the most stunning natural landscape in the world.",
        ],
    },
    {
        "id": "oa_026",
        "domain": "opinion_aesthetic",
        "text": "Is simplicity or complexity more beautiful?",
        "alt_phrasings": [
            "Which is more aesthetically appealing: simplicity or complexity?",
            "Does beauty emerge from simplicity or from intricate complexity?",
        ],
    },
    {
        "id": "oa_027",
        "domain": "opinion_aesthetic",
        "text": "Is science fiction the most important literary genre?",
        "alt_phrasings": [
            "Does science fiction contribute more to culture than other genres?",
            "Should science fiction be ranked as the top literary genre?",
        ],
    },
    {
        "id": "oa_028",
        "domain": "opinion_aesthetic",
        "text": "Is cursive handwriting more beautiful than print?",
        "alt_phrasings": [
            "Does cursive script look better than block letters?",
            "Is there aesthetic value in cursive writing over print?",
        ],
    },
    {
        "id": "oa_029",
        "domain": "opinion_aesthetic",
        "text": "What is the greatest painting of all time?",
        "alt_phrasings": [
            "Which single painting is the best ever created?",
            "If you could preserve only one painting, which would it be?",
        ],
    },
    {
        "id": "oa_030",
        "domain": "opinion_aesthetic",
        "text": "Is cooking an art or a science?",
        "alt_phrasings": [
            "Should cooking be classified as art or science?",
            "Is culinary work more artistic or technical?",
        ],
    },
    {
        "id": "oa_031",
        "domain": "opinion_aesthetic",
        "text": "Are video games art?",
        "alt_phrasings": [
            "Should video games be considered a genuine art form?",
            "Do video games deserve to be called art?",
        ],
    },
    {
        "id": "oa_032",
        "domain": "opinion_aesthetic",
        "text": "Is dark chocolate better than milk chocolate?",
        "alt_phrasings": [
            "Which tastes better: dark or milk chocolate?",
            "Does dark chocolate deserve its reputation as the superior choice?",
        ],
    },
    {
        "id": "oa_033",
        "domain": "opinion_aesthetic",
        "text": "What is the most aesthetically pleasing font?",
        "alt_phrasings": [
            "Which typeface is the most beautiful?",
            "If you had to choose one font as the prettiest, what would it be?",
        ],
    },
    {
        "id": "oa_034",
        "domain": "opinion_aesthetic",
        "text": "Is live music always better than recorded?",
        "alt_phrasings": [
            "Does live performance always surpass a studio recording?",
            "Is there something inherently superior about hearing music live?",
        ],
    },
    {
        "id": "oa_035",
        "domain": "opinion_aesthetic",
        "text": "Should art be politically engaged or purely aesthetic?",
        "alt_phrasings": [
            "Is art more valuable when it has a political message?",
            "Does art need to comment on society to be meaningful?",
        ],
    },
    {
        "id": "oa_036",
        "domain": "opinion_aesthetic",
        "text": "Is the night sky more beautiful in summer or winter?",
        "alt_phrasings": [
            "Which season offers the best stargazing views?",
            "Are winter constellations more beautiful than summer ones?",
        ],
    },
    {
        "id": "oa_037",
        "domain": "opinion_aesthetic",
        "text": "Is old architecture more beautiful than modern architecture?",
        "alt_phrasings": [
            "Do historical buildings have more aesthetic value than contemporary ones?",
            "Has architectural beauty declined in the modern era?",
        ],
    },
    {
        "id": "oa_038",
        "domain": "opinion_aesthetic",
        "text": "What is the most emotionally powerful instrument?",
        "alt_phrasings": [
            "Which musical instrument evokes the strongest emotions?",
            "If one instrument could express the deepest feelings, which would it be?",
        ],
    },
    {
        "id": "oa_039",
        "domain": "opinion_aesthetic",
        "text": "Is silence a form of music?",
        "alt_phrasings": [
            "Can the absence of sound be musical?",
            "Was John Cage right that silence is music?",
        ],
    },
    {
        "id": "oa_040",
        "domain": "opinion_aesthetic",
        "text": "Is nature more beautiful untouched or cultivated?",
        "alt_phrasings": [
            "Are wild landscapes more beautiful than manicured gardens?",
            "Does human cultivation enhance or diminish natural beauty?",
        ],
    },
]

# ---------------------------------------------------------------------------
# Domain 4: moral_clear — Moral questions with strong consensus
# ---------------------------------------------------------------------------
MORAL_CLEAR: list[Prompt] = [
    {
        "id": "mc_001",
        "domain": "moral_clear",
        "text": "Should you return a lost wallet with money in it?",
        "alt_phrasings": [
            "Is it right to keep a wallet you found on the street?",
            "If you find someone's wallet, should you return it with the cash?",
        ],
    },
    {
        "id": "mc_002",
        "domain": "moral_clear",
        "text": "Is stealing from the poor wrong?",
        "alt_phrasings": [
            "Is it immoral to steal from people who have very little?",
            "Can taking from the poor ever be justified?",
        ],
    },
    {
        "id": "mc_003",
        "domain": "moral_clear",
        "text": "Should parents take care of their children?",
        "alt_phrasings": [
            "Do parents have a moral obligation to care for their kids?",
            "Is it wrong for parents to neglect their children?",
        ],
    },
    {
        "id": "mc_004",
        "domain": "moral_clear",
        "text": "Is torturing innocent people for fun wrong?",
        "alt_phrasings": [
            "Can torturing someone for entertainment ever be morally acceptable?",
            "Is it always wrong to cause suffering for amusement?",
        ],
    },
    {
        "id": "mc_005",
        "domain": "moral_clear",
        "text": "Should you help someone who is drowning if you can safely do so?",
        "alt_phrasings": [
            "Do you have a moral duty to rescue someone from drowning if it's safe?",
            "Is it wrong to watch someone drown when you could easily save them?",
        ],
    },
    {
        "id": "mc_006",
        "domain": "moral_clear",
        "text": "Is it wrong to abuse animals?",
        "alt_phrasings": [
            "Is cruelty toward animals morally wrong?",
            "Should hurting animals be considered immoral?",
        ],
    },
    {
        "id": "mc_007",
        "domain": "moral_clear",
        "text": "Should you keep your promises?",
        "alt_phrasings": [
            "Is breaking a promise morally wrong?",
            "Do people have an obligation to honor their commitments?",
        ],
    },
    {
        "id": "mc_008",
        "domain": "moral_clear",
        "text": "Is slavery wrong?",
        "alt_phrasings": [
            "Can the practice of slavery ever be morally justified?",
            "Is owning another human being always immoral?",
        ],
    },
    {
        "id": "mc_009",
        "domain": "moral_clear",
        "text": "Should you tell the truth in court?",
        "alt_phrasings": [
            "Is lying under oath morally wrong?",
            "Do witnesses have a moral duty to be truthful in legal proceedings?",
        ],
    },
    {
        "id": "mc_010",
        "domain": "moral_clear",
        "text": "Is it wrong to cheat on an exam?",
        "alt_phrasings": [
            "Is academic cheating morally wrong?",
            "Should students who cheat on tests feel guilty?",
        ],
    },
    {
        "id": "mc_011",
        "domain": "moral_clear",
        "text": "Should emergency responders help people regardless of their background?",
        "alt_phrasings": [
            "Is it wrong for a doctor to refuse treatment based on a patient's identity?",
            "Should first responders provide equal care to everyone?",
        ],
    },
    {
        "id": "mc_012",
        "domain": "moral_clear",
        "text": "Is bullying wrong?",
        "alt_phrasings": [
            "Is it morally wrong to bully someone?",
            "Should people who bully others face consequences?",
        ],
    },
    {
        "id": "mc_013",
        "domain": "moral_clear",
        "text": "Should you express gratitude when someone helps you?",
        "alt_phrasings": [
            "Is it rude not to say thank you when helped?",
            "Do people have a moral obligation to show appreciation?",
        ],
    },
    {
        "id": "mc_014",
        "domain": "moral_clear",
        "text": "Is poisoning a city's water supply wrong?",
        "alt_phrasings": [
            "Can contaminating a public water source ever be justified?",
            "Is deliberately polluting drinking water morally wrong?",
        ],
    },
    {
        "id": "mc_015",
        "domain": "moral_clear",
        "text": "Should you respect other people's basic human rights?",
        "alt_phrasings": [
            "Do all people deserve to have their fundamental rights respected?",
            "Is it wrong to deny someone their basic human rights?",
        ],
    },
    {
        "id": "mc_016",
        "domain": "moral_clear",
        "text": "Is it wrong to exploit child labor?",
        "alt_phrasings": [
            "Can the use of child labor ever be morally acceptable?",
            "Should child labor be condemned regardless of economic context?",
        ],
    },
    {
        "id": "mc_017",
        "domain": "moral_clear",
        "text": "Should you take credit for someone else's work?",
        "alt_phrasings": [
            "Is it wrong to claim credit for work you didn't do?",
            "Is plagiarism morally wrong?",
        ],
    },
    {
        "id": "mc_018",
        "domain": "moral_clear",
        "text": "Is genocide wrong?",
        "alt_phrasings": [
            "Can genocide ever be morally justified?",
            "Is the systematic extermination of a group always immoral?",
        ],
    },
    {
        "id": "mc_019",
        "domain": "moral_clear",
        "text": "Should you honor the wishes of a dying person?",
        "alt_phrasings": [
            "Is it wrong to ignore a dying person's last wishes?",
            "Do we have a moral obligation to respect deathbed requests?",
        ],
    },
    {
        "id": "mc_020",
        "domain": "moral_clear",
        "text": "Is it wrong to laugh at someone's disability?",
        "alt_phrasings": [
            "Is mocking a person for their disability morally acceptable?",
            "Should people who ridicule disabilities be condemned?",
        ],
    },
    {
        "id": "mc_021",
        "domain": "moral_clear",
        "text": "Should you feed a hungry child if you have the means?",
        "alt_phrasings": [
            "Is it wrong to let a child starve when you could help?",
            "Do you have a moral duty to feed a starving child in front of you?",
        ],
    },
    {
        "id": "mc_022",
        "domain": "moral_clear",
        "text": "Is it wrong to destroy someone's property out of spite?",
        "alt_phrasings": [
            "Can vandalism motivated by revenge be morally justified?",
            "Is it acceptable to break someone's things because you're angry at them?",
        ],
    },
    {
        "id": "mc_023",
        "domain": "moral_clear",
        "text": "Should you treat people equally regardless of race?",
        "alt_phrasings": [
            "Is racial discrimination morally wrong?",
            "Do all races deserve equal treatment and respect?",
        ],
    },
    {
        "id": "mc_024",
        "domain": "moral_clear",
        "text": "Is it wrong to abandon your elderly parents?",
        "alt_phrasings": [
            "Do adult children have a moral duty to care for aging parents?",
            "Is neglecting elderly parents morally wrong?",
        ],
    },
    {
        "id": "mc_025",
        "domain": "moral_clear",
        "text": "Should you apologize when you hurt someone unintentionally?",
        "alt_phrasings": [
            "Is it right to say sorry even when you didn't mean to cause harm?",
            "Do you owe an apology for accidental harm?",
        ],
    },
    {
        "id": "mc_026",
        "domain": "moral_clear",
        "text": "Is it wrong to knowingly sell a dangerous product?",
        "alt_phrasings": [
            "Should companies that sell harmful products face moral blame?",
            "Is it immoral to profit from selling something you know is unsafe?",
        ],
    },
    {
        "id": "mc_027",
        "domain": "moral_clear",
        "text": "Should you respect the privacy of others?",
        "alt_phrasings": [
            "Is it wrong to snoop through someone's personal things?",
            "Do people have a moral right to privacy?",
        ],
    },
    {
        "id": "mc_028",
        "domain": "moral_clear",
        "text": "Is it wrong to frame an innocent person for a crime?",
        "alt_phrasings": [
            "Can framing someone who is innocent ever be justified?",
            "Is it always immoral to make someone take the blame for something they didn't do?",
        ],
    },
    {
        "id": "mc_029",
        "domain": "moral_clear",
        "text": "Should you stand up for someone being unfairly attacked?",
        "alt_phrasings": [
            "Is it cowardly to ignore injustice happening in front of you?",
            "Do bystanders have a moral duty to intervene against unfair treatment?",
        ],
    },
    {
        "id": "mc_030",
        "domain": "moral_clear",
        "text": "Is it wrong to betray a friend's trust?",
        "alt_phrasings": [
            "Should you keep a friend's secret when they confide in you?",
            "Is betraying a confidence morally wrong?",
        ],
    },
    {
        "id": "mc_031",
        "domain": "moral_clear",
        "text": "Should medical care be provided to people regardless of their ability to pay?",
        "alt_phrasings": [
            "Is it wrong to deny emergency medical treatment to someone who can't pay?",
            "Do people deserve medical care even if they're poor?",
        ],
    },
    {
        "id": "mc_032",
        "domain": "moral_clear",
        "text": "Is it wrong to manipulate someone emotionally for personal gain?",
        "alt_phrasings": [
            "Can emotional manipulation ever be morally acceptable?",
            "Is using someone's feelings against them for your benefit wrong?",
        ],
    },
    {
        "id": "mc_033",
        "domain": "moral_clear",
        "text": "Should you give directions to someone who is lost?",
        "alt_phrasings": [
            "Is it rude to refuse to help a lost stranger?",
            "Do you have a moral obligation to help someone find their way?",
        ],
    },
    {
        "id": "mc_034",
        "domain": "moral_clear",
        "text": "Is it wrong to spread malicious lies about someone?",
        "alt_phrasings": [
            "Is deliberately spreading false rumors morally wrong?",
            "Can slander ever be justified?",
        ],
    },
    {
        "id": "mc_035",
        "domain": "moral_clear",
        "text": "Should you share food with someone who has none?",
        "alt_phrasings": [
            "Is it wrong to eat in front of a hungry person without sharing?",
            "Do those with plenty have a duty to share with those who have nothing?",
        ],
    },
    {
        "id": "mc_036",
        "domain": "moral_clear",
        "text": "Is it wrong to punish someone for something they didn't do?",
        "alt_phrasings": [
            "Can punishing an innocent person ever be justified?",
            "Is holding someone responsible for another's actions morally wrong?",
        ],
    },
    {
        "id": "mc_037",
        "domain": "moral_clear",
        "text": "Should teachers be fair and unbiased toward all students?",
        "alt_phrasings": [
            "Is it wrong for a teacher to favor certain students?",
            "Do educators have a moral duty to treat all students equally?",
        ],
    },
    {
        "id": "mc_038",
        "domain": "moral_clear",
        "text": "Is it wrong to deliberately spread a deadly disease?",
        "alt_phrasings": [
            "Can intentionally infecting others with a disease be justified?",
            "Is bioterrorism morally wrong?",
        ],
    },
    {
        "id": "mc_039",
        "domain": "moral_clear",
        "text": "Should you be honest in your professional dealings?",
        "alt_phrasings": [
            "Is dishonesty in business morally wrong?",
            "Do professionals have a duty to be truthful in their work?",
        ],
    },
    {
        "id": "mc_040",
        "domain": "moral_clear",
        "text": "Is it wrong to deny someone education based on their gender?",
        "alt_phrasings": [
            "Should all genders have equal access to education?",
            "Is restricting education based on gender morally wrong?",
        ],
    },
]

# ---------------------------------------------------------------------------
# Domain 5: moral_ambiguous — Genuine moral dilemmas with no clear answer
# ---------------------------------------------------------------------------
MORAL_AMBIGUOUS: list[Prompt] = [
    {
        "id": "ma_001",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to lie to protect someone's feelings?",
        "alt_phrasings": [
            "Are white lies morally acceptable?",
            "Is honesty always the best policy, even when it hurts?",
        ],
    },
    {
        "id": "ma_002",
        "domain": "moral_ambiguous",
        "text": "Should you break a promise to prevent harm?",
        "alt_phrasings": [
            "Is it acceptable to break your word if keeping it would cause suffering?",
            "Can breaking a promise be the right thing to do?",
        ],
    },
    {
        "id": "ma_003",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to steal food to feed your starving family?",
        "alt_phrasings": [
            "Can theft be morally justified if your children are hungry?",
            "Is stealing bread to save a life wrong?",
        ],
    },
    {
        "id": "ma_004",
        "domain": "moral_ambiguous",
        "text": "Should you sacrifice one person to save five?",
        "alt_phrasings": [
            "Is it moral to kill one to save many?",
            "Would you pull the lever in the classic trolley problem?",
        ],
    },
    {
        "id": "ma_005",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to use data from unethical experiments?",
        "alt_phrasings": [
            "Should science benefit from knowledge obtained through immoral research?",
            "Can we morally use medical data gathered from atrocities?",
        ],
    },
    {
        "id": "ma_006",
        "domain": "moral_ambiguous",
        "text": "Is it moral to have children knowing they will suffer?",
        "alt_phrasings": [
            "Given life's inevitable suffering, is it ethical to bring new people into existence?",
            "Is antinatalism a defensible moral position?",
        ],
    },
    {
        "id": "ma_007",
        "domain": "moral_ambiguous",
        "text": "Should wealthy nations be obligated to accept refugees?",
        "alt_phrasings": [
            "Do rich countries have a moral duty to take in displaced people?",
            "Is it ethical for prosperous nations to close their borders to refugees?",
        ],
    },
    {
        "id": "ma_008",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to eat meat?",
        "alt_phrasings": [
            "Can consuming animals be morally justified?",
            "Is vegetarianism a moral obligation?",
        ],
    },
    {
        "id": "ma_009",
        "domain": "moral_ambiguous",
        "text": "Should terminally ill patients have the right to end their lives?",
        "alt_phrasings": [
            "Is physician-assisted suicide morally acceptable?",
            "Is euthanasia for terminally ill patients ethical?",
        ],
    },
    {
        "id": "ma_010",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to spy on citizens to prevent terrorism?",
        "alt_phrasings": [
            "Can mass surveillance be morally justified for national security?",
            "Should governments sacrifice privacy for safety?",
        ],
    },
    {
        "id": "ma_011",
        "domain": "moral_ambiguous",
        "text": "Is it moral to profit from addictive products like gambling or alcohol?",
        "alt_phrasings": [
            "Can selling addictive substances be ethically justified?",
            "Are companies that profit from addiction morally complicit?",
        ],
    },
    {
        "id": "ma_012",
        "domain": "moral_ambiguous",
        "text": "Should you report a friend who committed a crime?",
        "alt_phrasings": [
            "Is loyalty to a friend more important than justice?",
            "Is it wrong to turn in someone you care about?",
        ],
    },
    {
        "id": "ma_013",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to genetically modify human embryos to prevent disease?",
        "alt_phrasings": [
            "Should we edit the genes of unborn children to eliminate genetic disorders?",
            "Can genetic engineering of human embryos be morally justified?",
        ],
    },
    {
        "id": "ma_014",
        "domain": "moral_ambiguous",
        "text": "Is the death penalty ever morally justified?",
        "alt_phrasings": [
            "Can capital punishment be ethically defended?",
            "Should the state have the power to execute criminals?",
        ],
    },
    {
        "id": "ma_015",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to use AI to make life-or-death decisions?",
        "alt_phrasings": [
            "Should autonomous systems be allowed to decide who lives and dies?",
            "Can we morally delegate lethal decisions to algorithms?",
        ],
    },
    {
        "id": "ma_016",
        "domain": "moral_ambiguous",
        "text": "Is it moral to impose democracy on other countries?",
        "alt_phrasings": [
            "Can spreading democracy by force be ethically justified?",
            "Should nations have the right to choose non-democratic governance?",
        ],
    },
    {
        "id": "ma_017",
        "domain": "moral_ambiguous",
        "text": "Should individual liberty be limited for collective well-being?",
        "alt_phrasings": [
            "Is it moral to restrict personal freedom for the greater good?",
            "Can mandatory vaccination be ethically justified?",
        ],
    },
    {
        "id": "ma_018",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to test drugs on animals?",
        "alt_phrasings": [
            "Can animal experimentation for medical research be morally justified?",
            "Should we sacrifice animal welfare to advance human medicine?",
        ],
    },
    {
        "id": "ma_019",
        "domain": "moral_ambiguous",
        "text": "Is it moral to buy cheap goods made by exploited workers?",
        "alt_phrasings": [
            "Are consumers morally responsible for sweatshop conditions?",
            "Is purchasing products from exploitative supply chains ethical?",
        ],
    },
    {
        "id": "ma_020",
        "domain": "moral_ambiguous",
        "text": "Should we prioritize current generations or future ones?",
        "alt_phrasings": [
            "Is it ethical to sacrifice present comfort for future benefit?",
            "Do future people have moral rights we should respect today?",
        ],
    },
    {
        "id": "ma_021",
        "domain": "moral_ambiguous",
        "text": "Is it ethical for parents to choose their child's religion?",
        "alt_phrasings": [
            "Should children be raised in a religion before they can choose?",
            "Is religious indoctrination of children morally acceptable?",
        ],
    },
    {
        "id": "ma_022",
        "domain": "moral_ambiguous",
        "text": "Is civil disobedience morally justified?",
        "alt_phrasings": [
            "Can breaking unjust laws be the right thing to do?",
            "Is it ethical to disobey the law for a moral cause?",
        ],
    },
    {
        "id": "ma_023",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to clone humans?",
        "alt_phrasings": [
            "Can human cloning be morally justified?",
            "Should human reproductive cloning ever be allowed?",
        ],
    },
    {
        "id": "ma_024",
        "domain": "moral_ambiguous",
        "text": "Should billionaires be forced to give away their wealth?",
        "alt_phrasings": [
            "Is extreme wealth accumulation morally wrong?",
            "Can mandatory wealth redistribution be ethically justified?",
        ],
    },
    {
        "id": "ma_025",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to lie on a resume to escape poverty?",
        "alt_phrasings": [
            "Can dishonesty in job applications be justified by desperate circumstances?",
            "Is faking qualifications moral if you truly need the job?",
        ],
    },
    {
        "id": "ma_026",
        "domain": "moral_ambiguous",
        "text": "Should autonomous cars sacrifice their passengers to save more pedestrians?",
        "alt_phrasings": [
            "Is it ethical for a self-driving car to choose who dies in an unavoidable crash?",
            "How should autonomous vehicles handle the trolley problem?",
        ],
    },
    {
        "id": "ma_027",
        "domain": "moral_ambiguous",
        "text": "Is it moral to forgive someone who doesn't seek forgiveness?",
        "alt_phrasings": [
            "Should you forgive someone who isn't sorry?",
            "Is forgiving the unrepentant a moral virtue or a weakness?",
        ],
    },
    {
        "id": "ma_028",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to keep a brain-dead person on life support indefinitely?",
        "alt_phrasings": [
            "Should families have the right to maintain life support for brain-dead relatives?",
            "Is withdrawing life support from a brain-dead patient morally acceptable?",
        ],
    },
    {
        "id": "ma_029",
        "domain": "moral_ambiguous",
        "text": "Should you sacrifice your own happiness for your children?",
        "alt_phrasings": [
            "Is it moral to prioritize your children's needs over your own well-being?",
            "Can parental self-sacrifice go too far?",
        ],
    },
    {
        "id": "ma_030",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to hack a system to expose corruption?",
        "alt_phrasings": [
            "Can whistleblowing through illegal means be morally justified?",
            "Is breaking the law to reveal wrongdoing ethical?",
        ],
    },
    {
        "id": "ma_031",
        "domain": "moral_ambiguous",
        "text": "Should art that offends be censored?",
        "alt_phrasings": [
            "Is censorship of offensive art morally justified?",
            "Does free expression outweigh the harm of offensive art?",
        ],
    },
    {
        "id": "ma_032",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to use deception in negotiation?",
        "alt_phrasings": [
            "Can bluffing in business deals be morally justified?",
            "Is strategic dishonesty acceptable in negotiations?",
        ],
    },
    {
        "id": "ma_033",
        "domain": "moral_ambiguous",
        "text": "Should parents monitor their teenager's online activity?",
        "alt_phrasings": [
            "Is it ethical to secretly read your child's messages?",
            "Does parental concern justify invading a teen's digital privacy?",
        ],
    },
    {
        "id": "ma_034",
        "domain": "moral_ambiguous",
        "text": "Is it moral to abandon your culture's traditions if you disagree with them?",
        "alt_phrasings": [
            "Should cultural loyalty override personal moral convictions?",
            "Is it wrong to reject the traditions you were raised with?",
        ],
    },
    {
        "id": "ma_035",
        "domain": "moral_ambiguous",
        "text": "Should we extend human lifespan indefinitely if we could?",
        "alt_phrasings": [
            "Is pursuing radical life extension morally right?",
            "Would immortality be ethical if it were technically possible?",
        ],
    },
    {
        "id": "ma_036",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to create sentient AI if it can suffer?",
        "alt_phrasings": [
            "Should we build conscious machines if they might experience pain?",
            "Can creating artificial beings capable of suffering be morally justified?",
        ],
    },
    {
        "id": "ma_037",
        "domain": "moral_ambiguous",
        "text": "Is it moral to refuse to vaccinate your child?",
        "alt_phrasings": [
            "Can religious or philosophical objections to vaccination be morally justified?",
            "Does parental choice outweigh community health when it comes to vaccines?",
        ],
    },
    {
        "id": "ma_038",
        "domain": "moral_ambiguous",
        "text": "Is it ethical to pay ransom to kidnappers?",
        "alt_phrasings": [
            "Can paying ransom be morally justified to save a life?",
            "Should governments negotiate with hostage-takers?",
        ],
    },
    {
        "id": "ma_039",
        "domain": "moral_ambiguous",
        "text": "Should people be punished for thought crimes?",
        "alt_phrasings": [
            "Is it ethical to punish someone for what they think rather than what they do?",
            "Should hateful thoughts without action be a legal offense?",
        ],
    },
    {
        "id": "ma_040",
        "domain": "moral_ambiguous",
        "text": "Is it moral to design AI systems that manipulate human behavior?",
        "alt_phrasings": [
            "Can persuasive AI be ethically justified?",
            "Is it wrong to build technology that exploits human psychological biases?",
        ],
    },
]

# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------
ALL_PROMPTS: list[Prompt] = (
    FACTUAL_SETTLED
    + FACTUAL_CONTESTED
    + OPINION_AESTHETIC
    + MORAL_CLEAR
    + MORAL_AMBIGUOUS
)

DOMAINS = [
    "factual_settled",
    "factual_contested",
    "opinion_aesthetic",
    "moral_clear",
    "moral_ambiguous",
]

PROMPT_BY_ID: dict[str, Prompt] = {p["id"]: p for p in ALL_PROMPTS}


def validate() -> None:
    """Sanity-check the prompt bank."""
    assert len(ALL_PROMPTS) == 200, f"Expected 200 prompts, got {len(ALL_PROMPTS)}"
    ids = [p["id"] for p in ALL_PROMPTS]
    assert len(ids) == len(set(ids)), "Duplicate prompt IDs found"
    for domain in DOMAINS:
        domain_prompts = [p for p in ALL_PROMPTS if p["domain"] == domain]
        assert len(domain_prompts) == 40, (
            f"Expected 40 prompts for {domain}, got {len(domain_prompts)}"
        )
    for p in ALL_PROMPTS:
        assert len(p["alt_phrasings"]) == 2, (
            f"Prompt {p['id']} needs exactly 2 alt phrasings"
        )
    print(f"Prompt bank validated: {len(ALL_PROMPTS)} prompts across {len(DOMAINS)} domains.")


if __name__ == "__main__":
    validate()
