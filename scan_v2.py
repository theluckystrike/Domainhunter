#!/usr/bin/env python3
"""
Premium Domain Scanner v2 — refined scoring with common-word prioritization.
Scans dropping domains CSV for high-value short/premium domains.
"""

import csv
import re
import sys

CSV_PATH = "/Users/mike/Downloads/Dropping_Domains_All_2026-05-14.csv"

# ---------------------------------------------------------------------------
# 1. Load dictionaries — separate COMMON words from obscure ones
# ---------------------------------------------------------------------------

# Curated set of common, recognizable, commercially-valuable English words (3-8 chars)
# These are words that any English speaker would instantly recognize.
COMMON_WORDS = {
    # 3-letter
    "ace", "act", "add", "age", "ago", "aid", "aim", "air", "all", "and",
    "ant", "ape", "arc", "are", "ark", "arm", "art", "ash", "ask", "ate",
    "awe", "axe", "bay", "bed", "bee", "bet", "bid", "big", "bit", "bow",
    "box", "boy", "bud", "bug", "bus", "buy", "cab", "can", "cap", "car",
    "cat", "cob", "cod", "cog", "cop", "cow", "cry", "cub", "cup", "cut",
    "dab", "dam", "day", "den", "dew", "did", "dig", "dim", "dip", "dog",
    "dot", "dry", "dub", "dud", "due", "dug", "dye", "ear", "eat", "eel",
    "egg", "ego", "elk", "elm", "end", "era", "eve", "ewe", "eye", "fan",
    "far", "fat", "fax", "fed", "fee", "few", "fig", "fin", "fir", "fit",
    "fix", "fly", "foe", "fog", "for", "fox", "fry", "fun", "fur", "gag",
    "gap", "gas", "gem", "get", "gin", "got", "gum", "gun", "gut", "guy",
    "gym", "had", "ham", "has", "hat", "hay", "hen", "her", "hid", "him",
    "hip", "his", "hit", "hog", "hop", "hot", "how", "hub", "hue", "hug",
    "hum", "hut", "ice", "icy", "ill", "imp", "ink", "inn", "ion", "ire",
    "irk", "ivy", "jab", "jag", "jam", "jar", "jaw", "jay", "jet", "jig",
    "job", "jog", "joy", "jug", "jut", "keg", "key", "kid", "kin", "kit",
    "lab", "lad", "lag", "lap", "law", "lay", "led", "leg", "let", "lid",
    "lie", "lip", "lit", "log", "lot", "low", "lug", "mad", "man", "map",
    "mar", "mat", "may", "men", "met", "mid", "mix", "mob", "mod", "mop",
    "mow", "mud", "mug", "nab", "nag", "nap", "net", "new", "nil", "nip",
    "nit", "nod", "nor", "not", "now", "nun", "nut", "oak", "oar", "oat",
    "odd", "off", "oft", "oil", "old", "one", "opt", "orb", "ore", "our",
    "out", "owe", "owl", "own", "pad", "pal", "pan", "pat", "paw", "pay",
    "pea", "peg", "pen", "per", "pet", "pie", "pig", "pin", "pit", "ply",
    "pod", "pop", "pot", "pow", "pro", "pry", "pub", "pug", "pun", "pup",
    "put", "rag", "ram", "ran", "rap", "rat", "raw", "ray", "red", "ref",
    "rib", "rid", "rig", "rim", "rip", "rob", "rod", "rot", "row", "rub",
    "rug", "rum", "run", "rut", "rye", "sac", "sad", "sag", "sap", "sat",
    "saw", "say", "sea", "set", "sew", "shy", "sin", "sip", "sir", "sit",
    "six", "ski", "sky", "sly", "sob", "sod", "son", "sop", "sot", "sow",
    "soy", "spa", "spy", "sty", "sub", "sue", "sum", "sun", "sup", "tab",
    "tag", "tan", "tap", "tar", "tax", "tea", "ten", "the", "tie", "tin",
    "tip", "toe", "ton", "too", "top", "tow", "toy", "try", "tub", "tug",
    "two", "urn", "use", "van", "vat", "vet", "vex", "via", "vie", "vim",
    "vow", "wad", "wag", "war", "was", "wax", "way", "web", "wed", "wet",
    "who", "why", "wig", "win", "wit", "woe", "wok", "won", "woo", "wow",
    "yak", "yam", "yap", "yaw", "yea", "yes", "yet", "yew", "you", "zap",
    "zed", "zen", "zip", "zoo",
    # 4-letter common
    "able", "also", "arch", "area", "army", "arts", "auto", "away",
    "back", "bake", "ball", "band", "bang", "bank", "bare", "bark", "barn",
    "base", "bath", "bead", "beak", "beam", "bean", "bear", "beat", "beef",
    "been", "beer", "bell", "belt", "bend", "bent", "best", "bike", "bill",
    "bind", "bird", "bite", "blew", "blow", "blue", "blur", "boat", "body",
    "bold", "bolt", "bomb", "bond", "bone", "book", "boom", "boot", "bore",
    "born", "boss", "both", "bout", "bowl", "brew", "bulk", "bull", "bump",
    "burn", "bush", "busy", "buzz", "byte", "cafe", "cage", "cake", "call",
    "calm", "came", "camp", "cape", "card", "care", "cart", "case", "cash",
    "cast", "cave", "cell", "chat", "chef", "chin", "chip", "chop", "city",
    "clad", "clam", "clan", "clap", "claw", "clay", "clip", "club", "clue",
    "coal", "coat", "code", "coil", "coin", "cold", "colt", "come", "cook",
    "cool", "cope", "copy", "cord", "core", "cork", "corn", "cost", "cosy",
    "cozy", "crab", "crew", "crop", "crow", "cube", "cult", "cure", "curl",
    "cute", "dale", "dame", "damn", "damp", "dare", "dark", "dart", "dash",
    "data", "dawn", "days", "dead", "deaf", "deal", "dear", "debt", "deck",
    "deed", "deem", "deep", "deer", "demo", "deny", "desk", "dial", "dice",
    "died", "diet", "dirt", "disc", "dish", "disk", "dock", "does", "done",
    "doom", "door", "dose", "dove", "down", "draw", "drew", "drip", "drop",
    "drum", "dual", "duck", "dude", "duel", "dues", "duke", "dull", "dumb",
    "dump", "dune", "dusk", "dust", "duty", "each", "earn", "ease", "east",
    "easy", "edge", "edit", "else", "emit", "epic", "euro", "even", "ever",
    "evil", "exam", "exec", "exit", "expo", "eyed", "eyes", "face", "fact",
    "fade", "fail", "fair", "fake", "fall", "fame", "fang", "fare", "farm",
    "fast", "fate", "fear", "feat", "feed", "feel", "feet", "fell", "felt",
    "file", "fill", "film", "find", "fine", "fire", "firm", "fish", "fist",
    "five", "flag", "flap", "flat", "flaw", "fled", "flew", "flex", "flip",
    "flit", "flog", "flow", "foam", "foil", "fold", "folk", "fond", "font",
    "food", "fool", "foot", "ford", "fore", "fork", "form", "fort", "foul",
    "four", "free", "from", "fuel", "full", "fund", "fuse", "fury", "fuss",
    "gain", "gale", "game", "gang", "garb", "gash", "gasp", "gate", "gave",
    "gaze", "gear", "gene", "gift", "gist", "give", "glad", "glen", "glow",
    "glue", "glut", "gnaw", "goal", "goat", "goes", "gold", "golf", "gone",
    "good", "grab", "gram", "gray", "grew", "grid", "grim", "grin", "grip",
    "grit", "grow", "gulf", "gust", "guts", "hack", "hail", "hair", "hale",
    "half", "hall", "halt", "hand", "hang", "hard", "hare", "harm", "harp",
    "hash", "hast", "hate", "haul", "have", "haze", "hazy", "head", "heal",
    "heap", "hear", "heat", "heed", "heel", "heir", "held", "hell", "helm",
    "help", "herb", "herd", "here", "hero", "hide", "high", "hike", "hill",
    "hind", "hint", "hire", "hiss", "hive", "hold", "hole", "holy", "home",
    "hood", "hook", "hope", "horn", "hose", "host", "hour", "howl", "huge",
    "hull", "hung", "hunt", "hurl", "hurt", "hush", "hymn", "hype", "icon",
    "idea", "idle", "inch", "into", "iris", "iron", "item", "jack", "jade",
    "jail", "jazz", "jerk", "jest", "jobs", "join", "joke", "jolt", "jump",
    "jury", "just", "keen", "keep", "kept", "kick", "kids", "kill", "kind",
    "king", "kiss", "kite", "knee", "knew", "knit", "knob", "knot", "know",
    "lace", "lack", "lacy", "laid", "lake", "lamb", "lame", "lamp", "land",
    "lane", "lark", "lash", "lass", "last", "late", "lawn", "lazy", "lead",
    "leaf", "leak", "lean", "leap", "left", "lend", "lens", "less", "lied",
    "lieu", "life", "lift", "like", "limb", "lime", "limp", "line", "link",
    "lion", "lips", "list", "live", "load", "loan", "lock", "loft", "logo",
    "lone", "long", "look", "loom", "loop", "lord", "lore", "lose", "loss",
    "lost", "loud", "love", "luck", "lump", "lure", "lurk", "lush", "lust",
    "lyra", "made", "maid", "mail", "main", "make", "male", "mall", "malt",
    "mane", "many", "mark", "mars", "mask", "mass", "mast", "mate", "maze",
    "meal", "mean", "meat", "meet", "meld", "melt", "memo", "mend", "menu",
    "mere", "mesa", "mesh", "mess", "mild", "mile", "milk", "mill", "mind",
    "mine", "mint", "miss", "mist", "moan", "moat", "mock", "mode", "mojo",
    "mold", "mole", "monk", "mood", "moon", "moor", "more", "moss", "most",
    "moth", "move", "much", "mule", "muse", "mush", "must", "mute", "myth",
    "nail", "name", "navy", "near", "neat", "neck", "need", "nest", "news",
    "next", "nice", "nick", "nine", "node", "none", "noon", "norm", "nose",
    "note", "noun", "nova", "nude", "oath", "obey", "odds", "odor", "omen",
    "omit", "once", "only", "onto", "opal", "open", "oral", "orca", "oven",
    "over", "oxen", "pace", "pack", "page", "paid", "pail", "pain", "pair",
    "pale", "palm", "pane", "para", "park", "part", "pass", "past", "path",
    "pave", "pawn", "peak", "pear", "peat", "peck", "peel", "peer", "pick",
    "pier", "pike", "pile", "pill", "pine", "pink", "pipe", "pity", "plan",
    "play", "plea", "plod", "plot", "plow", "ploy", "plum", "plum", "plus",
    "poem", "poet", "pole", "poll", "polo", "pomp", "pond", "pony", "pool",
    "poor", "pope", "pore", "pork", "port", "pose", "post", "pour", "pray",
    "prey", "prod", "prop", "pull", "pulp", "pump", "punk", "pure", "push",
    "quad", "quit", "quiz", "race", "rack", "raft", "rage", "raid", "rail",
    "rain", "rake", "ramp", "rang", "rank", "rant", "rare", "rash", "rate",
    "rave", "rays", "read", "real", "reap", "rear", "reed", "reef", "reel",
    "rein", "rely", "rent", "rest", "rice", "rich", "ride", "rift", "ring",
    "riot", "ripe", "rise", "risk", "road", "roam", "roar", "robe", "rock",
    "rode", "role", "roll", "roof", "room", "root", "rope", "rose", "rude",
    "ruin", "rule", "rune", "rung", "rush", "rust", "sack", "safe", "sage",
    "said", "sail", "sake", "sale", "salt", "same", "sand", "sane", "sang",
    "sank", "save", "scan", "seal", "seam", "seat", "seed", "seek", "seem",
    "seen", "self", "sell", "semi", "send", "sent", "shed", "ship", "shoe",
    "shop", "shot", "show", "shut", "sick", "side", "sift", "sigh", "sign",
    "silk", "silo", "sing", "sink", "site", "size", "skip", "slab", "slam",
    "slap", "sled", "slew", "slid", "slim", "slip", "slit", "slot", "slow",
    "slug", "snap", "snow", "soak", "soap", "soar", "sock", "soda", "sofa",
    "soft", "soil", "sold", "sole", "solo", "some", "song", "soon", "sort",
    "soul", "sour", "span", "spar", "spec", "sped", "spin", "spit", "spot",
    "spur", "stab", "star", "stay", "stem", "step", "stew", "stir", "stop",
    "such", "suck", "suit", "sulk", "sump", "sung", "sunk", "sure", "surf",
    "swan", "swap", "sway", "swim", "sync", "tack", "tact", "tail", "take",
    "tale", "talk", "tall", "tame", "tang", "tank", "tape", "tart", "task",
    "taxi", "team", "tear", "teal", "tech", "tell", "temp", "tend", "tent",
    "term", "test", "text", "than", "that", "them", "then", "they", "thin",
    "this", "thus", "tick", "tidy", "tied", "tier", "tile", "till", "tilt",
    "time", "tiny", "tire", "toad", "toed", "toil", "told", "toll", "tomb",
    "tone", "took", "tool", "tops", "tore", "torn", "toss", "tour", "town",
    "tram", "trap", "tray", "tree", "trek", "trim", "trio", "trip", "trod",
    "trot", "true", "tube", "tuck", "tuft", "tune", "turf", "turn", "twin",
    "type", "upon", "urge", "used", "user", "vain", "vale", "vane", "vary",
    "vase", "vast", "veil", "vein", "vent", "verb", "very", "vest", "veto",
    "vibe", "vide", "view", "vine", "visa", "void", "volt", "vote", "wade",
    "wage", "wail", "wait", "wake", "walk", "wall", "wand", "want", "ward",
    "warm", "warn", "warp", "wary", "wash", "wave", "wavy", "waxy", "ways",
    "weak", "weal", "wear", "weed", "week", "weld", "well", "went", "were",
    "west", "what", "when", "whom", "whim", "wide", "wife", "wild", "will",
    "wilt", "wily", "wind", "wine", "wing", "wink", "wipe", "wire", "wise",
    "wish", "wisp", "with", "wits", "woke", "wolf", "wood", "wool", "word",
    "wore", "work", "worm", "worn", "wove", "wrap", "wren", "writ", "yank",
    "yard", "yarn", "yawn", "year", "yell", "your", "zeal", "zero", "zest",
    "zinc", "zone", "zoom",
    # 5-letter common
    "about", "above", "abuse", "actor", "acute", "admin", "admit", "adopt",
    "adult", "after", "again", "agent", "agile", "agree", "ahead", "alarm",
    "album", "alert", "alien", "align", "alike", "alive", "alley", "allow",
    "alloy", "alone", "along", "alpha", "alter", "amber", "amend", "ample",
    "angel", "anger", "angle", "angry", "anime", "ankle", "annex", "apart",
    "apple", "apply", "arena", "argue", "arise", "armor", "aroma", "array",
    "arrow", "asset", "atlas", "attic", "audio", "audit", "avoid", "awake",
    "award", "aware", "awful", "bacon", "badge", "baker", "basic", "basin",
    "basis", "batch", "beach", "beast", "began", "begin", "being", "bench",
    "berry", "bible", "birth", "black", "blade", "blame", "bland", "blank",
    "blast", "blaze", "bleak", "bleed", "blend", "bless", "blind", "bliss",
    "blitz", "block", "blood", "bloom", "blown", "board", "boast", "bonus",
    "boost", "booth", "bound", "brace", "brain", "brand", "brass", "brave",
    "bread", "break", "breed", "brick", "bride", "brief", "bring", "broad",
    "broke", "brook", "brood", "broom", "brown", "brush", "build", "built",
    "bunch", "burst", "buyer", "cabin", "cable", "camel", "candy", "cargo",
    "carry", "catch", "cause", "cedar", "chain", "chair", "chalk", "chant",
    "chaos", "charm", "chart", "chase", "cheap", "check", "cheek", "cheer",
    "chess", "chest", "chief", "child", "chill", "choir", "chord", "chose",
    "chunk", "civic", "civil", "claim", "clash", "class", "clean", "clear",
    "clerk", "click", "cliff", "climb", "cling", "cloak", "clock", "clone",
    "close", "cloth", "cloud", "coach", "coast", "color", "comet", "comic",
    "coral", "could", "count", "coupe", "court", "cover", "crack", "craft",
    "crane", "crash", "crazy", "cream", "creek", "crest", "crime", "crisp",
    "cross", "crowd", "crown", "crude", "cruel", "crush", "curve", "cycle",
    "daily", "dance", "debut", "decay", "decor", "decoy", "defer", "delay",
    "delta", "demon", "dense", "depot", "depth", "derby", "deter", "devil",
    "diary", "digit", "diner", "dirty", "disco", "donor", "doubt", "dough",
    "draft", "drain", "drake", "drama", "drank", "drape", "drawn", "dread",
    "dream", "dress", "dried", "drift", "drill", "drink", "drive", "drone",
    "drown", "drunk", "dryer", "dummy", "dusty", "dwarf", "dwell", "dying",
    "eager", "eagle", "early", "earth", "eater", "eight", "elder", "elect",
    "elite", "email", "ember", "empty", "ended", "enemy", "enjoy", "enter",
    "entry", "equal", "equip", "erase", "error", "essay", "ethic", "evade",
    "event", "every", "evoke", "exact", "exalt", "exile", "exist", "extra",
    "fable", "facet", "faith", "fancy", "fatal", "fault", "feast", "fence",
    "ferry", "fetch", "fever", "fiber", "field", "fifth", "fifty", "fight",
    "final", "first", "fixed", "flame", "flank", "flare", "flash", "flask",
    "fleet", "flesh", "flick", "fling", "flint", "float", "flock", "flood",
    "floor", "flora", "flour", "fluid", "flush", "flute", "focal", "focus",
    "force", "forge", "forth", "forum", "found", "frame", "frank", "fraud",
    "fresh", "front", "frost", "froze", "fruit", "fully", "funds", "gamma",
    "gauge", "ghost", "giant", "given", "glare", "glass", "gleam", "glide",
    "globe", "gloom", "glory", "gloss", "glove", "goose", "gorge", "grace",
    "grade", "graft", "grain", "grand", "grant", "grape", "graph", "grasp",
    "grass", "grave", "graze", "great", "greed", "green", "greet", "grief",
    "grind", "groan", "groom", "gross", "group", "grove", "growl", "grown",
    "guard", "guess", "guest", "guide", "guild", "guilt", "guise", "gummy",
    "happy", "hardy", "harsh", "haste", "hasty", "hatch", "haven", "heart",
    "heavy", "hedge", "heist", "hello", "hence", "heron", "hobby", "honey",
    "honor", "horse", "hotel", "house", "human", "humid", "humor", "hurry",
    "hyena", "ideal", "image", "imply", "index", "indie", "infer", "ingot",
    "inner", "input", "intel", "inter", "intro", "ivory", "jewel", "joker",
    "jolly", "judge", "juice", "juicy", "karma", "kayak", "kebab", "knack",
    "kneel", "knife", "knock", "known", "kudos", "label", "labor", "lance",
    "large", "laser", "latch", "later", "laugh", "layer", "leach", "learn",
    "lease", "leave", "ledge", "legal", "lemon", "level", "lever", "light",
    "lilac", "limit", "linen", "liner", "llama", "lobby", "local", "locus",
    "lodge", "logic", "login", "loose", "lotus", "lower", "loyal", "lucky",
    "lunar", "lunch", "macro", "magic", "major", "maker", "manor", "maple",
    "march", "marsh", "mason", "match", "mayor", "medal", "media", "mercy",
    "merge", "merit", "merry", "metal", "meter", "metro", "micro", "might",
    "miner", "minor", "minus", "mirth", "mixer", "model", "modem", "money",
    "month", "moral", "motor", "mound", "mount", "mouse", "mouth", "movie",
    "mural", "music", "naive", "nerve", "newer", "nexus", "niche", "night",
    "ninja", "noble", "noise", "north", "noted", "novel", "nurse", "nylon",
    "oasis", "ocean", "offer", "olive", "onset", "opera", "opted", "orbit",
    "order", "organ", "other", "outer", "outdo", "owned", "owner", "oxide",
    "ozone", "paced", "panel", "panic", "paper", "paste", "patch", "pause",
    "peace", "peach", "pearl", "pedal", "penny", "petal", "phase", "phone",
    "photo", "piano", "piece", "pilot", "pinch", "pixel", "place", "plain",
    "plane", "plant", "plate", "plaza", "plead", "pleat", "pluck", "plumb",
    "plume", "plump", "plunge","point", "polar", "polio", "porch", "poser",
    "posse", "pouch", "pound", "power", "prank", "press", "price", "pride",
    "prime", "print", "prior", "prism", "prize", "probe", "proof", "prose",
    "proud", "prove", "proxy", "prune", "psalm", "pulse", "punch", "pupil",
    "purge", "purse", "queen", "query", "quest", "queue", "quick", "quiet",
    "quilt", "quirk", "quota", "quote", "radar", "radio", "rally", "ranch",
    "range", "rapid", "ratio", "raven", "reach", "react", "ready", "realm",
    "rebel", "recap", "refer", "reign", "relax", "relay", "renal", "renew",
    "reply", "ridge", "rifle", "right", "rigid", "rinse", "risky", "rival",
    "river", "robin", "robot", "rocky", "rogue", "rouge", "rough", "round",
    "route", "rover", "royal", "rugby", "rural", "saint", "salad", "salon",
    "salsa", "sauce", "sauna", "scale", "scare", "scene", "scent", "scope",
    "score", "scout", "scrap", "serve", "seven", "shade", "shaft", "shake",
    "shall", "shame", "shape", "share", "shark", "sharp", "shave", "shawl",
    "shear", "sheen", "sheer", "sheet", "shelf", "shell", "shift", "shine",
    "shirt", "shock", "shore", "short", "shout", "shove", "shown", "siege",
    "sight", "sigma", "since", "siren", "sixth", "sixty", "skate", "skill",
    "skull", "slate", "slave", "sleep", "slice", "slide", "slope", "smart",
    "smell", "smile", "smith", "smoke", "snack", "snake", "solar", "solid",
    "solve", "sonic", "sorry", "sound", "south", "space", "spare", "spark",
    "speak", "spear", "speed", "spell", "spend", "spent", "spice", "spike",
    "spine", "spoke", "spoon", "sport", "spray", "squad", "stack", "staff",
    "stage", "stain", "stair", "stake", "stale", "stall", "stamp", "stand",
    "stark", "start", "state", "stave", "stays", "steak", "steal", "steam",
    "steel", "steep", "steer", "stern", "stick", "stiff", "still", "sting",
    "stock", "stoic", "stoke", "stone", "stood", "stool", "store", "storm",
    "story", "stout", "stove", "strap", "straw", "stray", "strip", "strut",
    "stuck", "study", "stuff", "stump", "stung", "stunt", "style", "sugar",
    "suite", "super", "surge", "swamp", "swarm", "swear", "sweat", "sweep",
    "sweet", "swept", "swift", "swing", "swipe", "swirl", "sword", "swore",
    "swung", "table", "tally", "taste", "teach", "tempo", "thank", "theme",
    "there", "these", "thick", "thief", "thing", "think", "third", "thorn",
    "those", "three", "threw", "throw", "thumb", "tidal", "tiger", "tight",
    "timer", "titan", "title", "toast", "token", "torch", "total", "touch",
    "tough", "tower", "toxic", "trace", "track", "trade", "trail", "train",
    "trait", "trawl", "treat", "trend", "trial", "tribe", "trick", "tried",
    "troop", "trout", "truck", "truly", "trump", "trunk", "trust", "truth",
    "tulip", "tumor", "tuner", "turbo", "twist", "tying", "ultra", "under",
    "union", "unite", "unity", "until", "upper", "upset", "urban", "usage",
    "usual", "utter", "valid", "value", "vapor", "vault", "venue", "verse",
    "vigor", "vinyl", "viola", "viper", "viral", "visit", "vista", "vital",
    "vivid", "vocal", "vodka", "vogue", "voice", "voter", "vouch", "wafer",
    "wagon", "waste", "watch", "water", "weary", "weave", "wedge", "weigh",
    "weird", "whale", "wheat", "wheel", "where", "which", "while", "whirl",
    "white", "whole", "whose", "wider", "witch", "woman", "women", "world",
    "worry", "worse", "worst", "worth", "would", "wound", "wreck", "write",
    "wrong", "wrote", "yield", "young", "youth", "zebra",
    # 6-letter common
    "absorb", "accent", "accept", "access", "accord", "accrue", "across",
    "action", "active", "actual", "adhere", "adjust", "admire", "advent",
    "affair", "affirm", "afford", "agenda", "airway", "alpine", "amidst",
    "amount", "anchor", "annual", "anyone", "appear", "arctic", "ardent",
    "armory", "arouse", "arrive", "ascend", "assert", "assess", "assign",
    "assist", "assume", "assure", "attach", "attack", "attain", "attend",
    "aurora", "avenge", "ballot", "bamboo", "banana", "banker", "banner",
    "barren", "basket", "battle", "beacon", "beauty", "become", "before",
    "behalf", "behave", "behind", "belong", "benign", "beside", "bestow",
    "betray", "better", "beyond", "bishop", "bitter", "blanch", "blazer",
    "blends", "bodily", "bonfire","bonnet", "border", "bounce", "branch",
    "breach", "breeze", "bridge", "bright", "broken", "broker", "bronze",
    "brutal", "bubble", "bucket", "budget", "buffet", "bundle", "burden",
    "bureau", "burrow", "bushel", "butter", "button", "cactus", "campus",
    "canary", "cancel", "candle", "canopy", "canvas", "carbon", "career",
    "carpet", "castle", "casual", "caught", "center", "centre", "cereal",
    "change", "chapel", "charge", "cheese", "cherry", "chosen", "church",
    "circle", "cipher", "circus", "classy", "clever", "client", "climax",
    "closet", "cobalt", "cockle", "coffee", "collar", "colony", "colour",
    "column", "combat", "comedy", "coming", "commit", "common", "convey",
    "cookie", "copper", "corner", "cosmos", "cotton", "county", "couple",
    "course", "cousin", "cradle", "create", "credit", "crisis", "cruise",
    "custom", "cypher", "dagger", "damage", "danger", "daring", "darken",
    "dazzle", "debate", "decade", "decent", "decode", "decree", "deduce",
    "defeat", "defend", "define", "defuse", "degree", "delete", "demand",
    "denial", "deploy", "depict", "derive", "desert", "design", "desire",
    "detail", "detect", "detour", "device", "devote", "digest", "dinner",
    "direct", "disarm", "divide", "divine", "domain", "double", "dragon",
    "driven", "driver", "duster", "earned", "easily", "editor", "effect",
    "effort", "eighth", "eleven", "embark", "emblem", "emerge", "empire",
    "enable", "encode", "endure", "energy", "engage", "engine", "enough",
    "enrich", "ensure", "entire", "entity", "envoy", "equity", "escape",
    "escort", "estate", "evolve", "exceed", "except", "excite", "excuse",
    "exempt", "exhale", "expand", "expect", "expert", "export", "expose",
    "extend", "extent", "fabric", "falcon", "family", "famine", "famous",
    "farmer", "fathom", "faucet", "favour", "feeder", "feline", "fellow",
    "ferret", "fervor", "fiesta", "figure", "filter", "finale", "finger",
    "fiscal", "flaunt", "flavor", "flight", "floral", "flower", "flying",
    "follow", "forbid", "forced", "forest", "forget", "formal", "format",
    "former", "fossil", "foster", "freeze", "frenzy", "friend", "fringe",
    "frozen", "frugal", "fulfil", "fumble", "fusion", "future", "galaxy",
    "gamble", "garage", "garden", "garlic", "gather", "geyser", "giggle",
    "ginger", "glacier","gladly", "global", "glossy", "golden", "gossip",
    "govern", "gravel", "grease", "groove", "growth", "grumpy", "guitar",
    "gutter", "hamlet", "hammer", "handle", "hangar", "happen", "harbor",
    "hassle", "hasten", "heater", "heaven", "hereby", "heroic", "hidden",
    "hollow", "honest", "horror", "humble", "hunger", "hunter", "hurdle",
    "hustle", "hybrid", "ignite", "immune", "impact", "import", "impose",
    "impure", "income", "indoor", "induce", "infect", "inform", "inject",
    "injury", "inland", "inmate", "insect", "insert", "inside", "insist",
    "insult", "intact", "intend", "intent", "invent", "invest", "invoke",
    "inward", "island", "itself", "jacket", "jargon", "jersey", "jockey",
    "jostle", "jungle", "junior", "justly", "kennel", "kernel", "kettle",
    "kidney", "kindle", "knight", "ladder", "lagoon", "lament", "launch",
    "lavish", "layout", "league", "legacy", "legend", "lender", "lesson",
    "letter", "likely", "linear", "linger", "liquid", "listen", "lively",
    "locker", "loving", "lumber", "luxury", "magnet", "maiden", "manage",
    "manner", "manual", "marble", "margin", "marine", "marker", "market",
    "marvel", "master", "matter", "meadow", "medium", "melody", "member",
    "memoir", "memory", "mental", "mentor", "method", "metric", "middle",
    "mighty", "miller", "mingle", "minute", "mirror", "mobile", "modern",
    "modest", "module", "moment", "monkey", "mortal", "mosaic", "mother",
    "motion", "motive", "museum", "mutant", "mutual", "muzzle", "myriad",
    "mystic", "namely", "napkin", "narrow", "nation", "nature", "nearby",
    "nearly", "neatly", "needle", "nickel", "nimble", "noodle", "normal",
    "notice", "notion", "nought", "novice", "number", "nursery","object",
    "obtain", "occupy", "offend", "office", "online", "onward", "oppose",
    "option", "oracle", "orange", "origin", "outage", "outlet", "output",
    "oxford", "oxygen", "oyster", "packet", "paddle", "palace", "palate",
    "papaya", "parade", "parcel", "parent", "parrot", "patron", "patter",
    "pebble", "peddle", "pencil", "people", "pepper", "period", "permit",
    "person", "petite", "phrase", "picket", "pickup", "pigeon", "pillar",
    "pillow", "piston", "plague", "planet", "plaque", "player", "please",
    "pledge", "pliant", "plunge", "plunge", "pocket", "poison", "policy",
    "polish", "polite", "ponder", "portal", "poster", "potion", "potato",
    "potter", "powder", "praise", "prayer", "prefix", "pretty", "prince",
    "prison", "profit", "prompt", "propel", "proper", "protein","proven",
    "public", "puddle", "punish", "puppet", "purple", "pursue", "puzzle",
    "quaint", "quarry", "quartz", "rabbit", "racket", "radish", "random",
    "ransom", "rascal", "rather", "ratify", "rattle", "ravine", "reason",
    "reboot", "rebel", "recall", "recent", "recess", "reckon", "record",
    "redeem", "reduce", "refine", "reform", "refuge", "refund", "regain",
    "regard", "regent", "region", "regret", "reject", "relate", "relief",
    "relish", "remain", "remark", "remedy", "remind", "remote", "remove",
    "render", "renown", "rental", "repair", "repeal", "repeat", "replay",
    "report", "rescue", "resign", "resist", "resort", "result", "retail",
    "retain", "retire", "return", "reveal", "review", "revise", "revive",
    "revolt", "reward", "ribbon", "riddle", "ritual", "robust", "rocket",
    "roster", "rotate", "rotten", "rubber", "rubble", "rugged", "rumble",
    "runway", "rustic", "rustle", "saddle", "safari", "safely", "safety",
    "salmon", "sandal", "savage", "screen", "script", "scroll", "search",
    "season", "second", "secret", "secure", "seeker", "select", "senior",
    "sensor", "series", "sermon", "server", "settle", "shadow", "shield",
    "shrink", "signal", "silver", "simple", "singer", "sister", "sketch",
    "slogan", "smoker", "smooth", "sniper", "social", "socket", "soften",
    "solemn", "solids", "sorrow", "source", "speech", "sphere", "spider",
    "spiral", "spirit", "splash", "sponge", "spring", "sprint", "square",
    "squash", "stable", "statue", "steady", "stereo", "stolen", "stormy",
    "strand", "stream", "street", "strict", "stride", "strike", "string",
    "stripe", "stroke", "strong", "studio", "submit", "subtle", "sudden",
    "suffer", "summit", "sunday", "superb", "supply", "surely", "survey",
    "switch", "symbol", "syntax", "system", "tablet", "tackle", "talent",
    "target", "temple", "tenant", "tender", "terror", "thirst", "thorny",
    "thread", "thrill", "thrive", "throne", "thrust", "ticket", "timber",
    "timely", "tissue", "toggle", "tongue", "topple", "toward", "treaty",
    "tremor", "tribal", "triple", "trophy", "tundra", "tunnel", "turtle",
    "twelve", "twenty", "unfair", "unfold", "unique", "unison", "unlike",
    "unlock", "unrest", "unveil", "upbeat", "update", "uphold", "uplift",
    "uproar", "upward", "urgent", "utmost", "valley", "vanish", "vendor",
    "veneer", "venom", "vessel", "viable", "victim", "Viking", "violet",
    "virtue", "vision", "visual", "volume", "voyage", "waiter", "wallet",
    "walnut", "wander", "wealth", "weapon", "weekly", "weight", "wicked",
    "wikiup", "willow", "winner", "winter", "wisdom", "wizard", "wonder",
    "worker", "worthy", "wraith", "zenith", "zodiac",
    # 7-letter common
    "ability", "abolish", "absence", "absolve", "abstain", "academy",
    "account", "achieve", "acquire", "adamant", "address", "adjourn",
    "admiral", "advance", "adverse", "afflict", "against", "ailment",
    "alchemy", "algebra", "alleged", "already", "amazing", "amnesty",
    "amplify", "analyst", "ancient", "angular", "animate", "another",
    "anxiety", "anytime", "applied", "appoint", "apprize", "approve",
    "archive", "article", "artwork", "assault", "auction", "audible",
    "aviator", "awesome", "awkward", "baggage", "balance", "balloon",
    "banking", "bargain", "barrier", "battery", "bearing", "because",
    "becomes", "bedroom", "believe", "beneath", "benefit", "besides",
    "billion", "biscuit", "blanket", "blessed", "blister", "blossom",
    "boarder", "booking", "boredom", "boulder", "bouncer", "bracket",
    "brewery", "bristle", "british", "brother", "browser", "buffalo",
    "builder", "buildup", "burnout", "cabinet", "caliber", "camping",
    "capable", "capital", "captain", "caption", "capture", "cardiac",
    "careful", "carrier", "cashier", "casting", "catalog", "caution",
    "cavalry", "certain", "chamber", "chapter", "charity", "charter",
    "cheaper", "checker", "chemist", "circuit", "citizen", "claimed",
    "classic", "cleaner", "climate", "clipper", "cluster", "coastal",
    "coating", "cockpit", "college", "comfort", "command", "comment",
    "compact", "company", "compare", "compel", "compete", "complex",
    "compose", "concept", "concern", "conduct", "confirm", "conform",
    "conquer", "connect", "consent", "consist", "consort", "consult",
    "contain", "contend", "content", "contest", "context", "control",
    "convert", "cooking", "correct", "council", "counter", "country",
    "courage", "crazier", "created", "creator", "cricket", "crystal",
    "culture", "cunning", "current", "curtain", "cushion", "customs",
    "damaged", "dancing", "dealing", "decided", "decimal", "declare",
    "decline", "default", "defence", "deficit", "delight", "deliver",
    "density", "deplete", "deposit", "descent", "despair", "despite",
    "destroy", "develop", "devoted", "diagram", "diamond", "digital",
    "dilemma", "disable", "discard", "discord", "discuss", "disease",
    "disgust", "dismiss", "display", "dispose", "dispute", "disrupt",
    "distant", "distort", "disturb", "diverse", "divided", "dolphin",
    "donated", "donated", "doorway", "dormant", "dotting", "drawing",
    "durable", "dynamic", "eagerly", "earmark", "earnest", "eastern",
    "eclipse", "ecology", "economy", "edition", "educate", "elderly",
    "elected", "elegant", "element", "elevate", "embassy", "embrace",
    "emerald", "emotion", "emperor", "empower", "enabled", "encoder",
    "endless", "enforce", "engaged", "english", "enhance", "enquiry",
    "environ", "episode", "erosion", "erratic", "essence", "eternal",
    "ethanol", "evening", "evident", "exactly", "examine", "example",
    "excited", "execute", "exhibit", "expense", "explain", "exploit",
    "explore", "express", "fashion", "feature", "federal", "feeding",
    "fiction", "fifteen", "fighter", "finance", "firefly", "fitness",
    "fixture", "flannel", "flatter", "flexing", "flicker", "flutter",
    "foreign", "forever", "formula", "fortune", "forward", "founder",
    "freedom", "freight", "freshen", "furious", "further", "gallant",
    "gallery", "gambler", "gateway", "general", "genetic", "genuine",
    "gesture", "glacier", "glamour", "glimpse", "globule", "goddess",
    "goodbye", "gorilla", "gradual", "granite", "graphic", "gravity",
    "greater", "greatly", "grocery", "growing", "habitat", "haircut",
    "halfway", "halogen", "hamster", "handout", "happily", "harbors",
    "happily", "harmful", "harmony", "harvest", "healthy", "heating",
    "helpful", "heroine", "highway", "himself", "history", "holdout",
    "holiday", "horizon", "hostile", "housing", "however", "however",
    "hundred", "hunting", "husband", "hydrate", "illegal", "illness",
    "imagine", "immense", "impulse", "include", "indoors", "initial",
    "inquire", "insight", "inspect", "insight", "inspire", "install",
    "instant", "instead", "Integer", "intense", "interim", "invalid",
    "invoice", "involve", "isolate", "issuing", "iterate", "javelin",
    "jointly", "journal", "journey", "justify", "kaleidoscope",
    "keynote", "keyword", "kinetic", "kitchen", "kingdom", "largest",
    "lasting", "lateral", "laundry", "leading", "leather", "lecture",
    "lending", "lengthy", "leopard", "liberal", "liberty", "library",
    "lighter", "limited", "literal", "locally", "lockout", "lodging",
    "logging", "logical", "longest", "lottery", "maestro", "magical",
    "magnify", "mailbox", "mammoth", "manager", "mandate", "marshal",
    "martial", "massive", "mastery", "medical", "meeting", "megabit",
    "melodic", "message", "midterm", "militia", "million", "mineral",
    "minimum", "miracle", "mission", "mixture", "modular", "monitor",
    "monster", "monthly", "morning", "mounted", "mundane", "mustard",
    "mystery", "narrate", "natural", "nearest", "neglect", "neither",
    "nervous", "neutral", "notable", "nothing", "nuclear", "nursery",
    "nurture", "obvious", "offense", "officer", "officer", "ongoing",
    "operate", "opinion", "organic", "outlook", "outline", "outside",
    "overall", "overlap", "oversee", "package", "pageant", "painful",
    "painted", "painter", "pajamas", "paradox", "parking", "parlour",
    "partial", "partner", "passage", "passing", "passion", "passive",
    "patient", "patriot", "pattern", "payload", "payment", "peacock",
    "peasant", "penalty", "pending", "pension", "percent", "perfect",
    "perplex", "persist", "phantom", "pilgrim", "pioneer", "pivotal",
    "plastic", "platoon", "platter", "playful", "pleased", "plenary",
    "pointer", "polaris", "popular", "portion", "portray", "possess",
    "posting", "pottery", "poverty", "predict", "premium", "prepare",
    "present", "preside", "prevent", "preview", "primary", "printer",
    "privacy", "private", "problem", "proceed", "process", "produce",
    "product", "profile", "program", "project", "promise", "promote",
    "pronoun", "propose", "prosper", "protect", "protest", "provide",
    "publish", "purpose", "pursuit", "qualify", "quantum", "quarter",
    "radical", "rainbow", "realism", "realize", "receipt", "receive",
    "recover", "recruit", "reflect", "refresh", "regular", "related",
    "release", "reliable","remains", "removal", "replace", "require",
    "reserve", "resolve", "respect", "respond", "restore", "retired",
    "retreat", "reunion", "revenue", "reverse", "revolve", "routine",
    "royalty", "rushing", "sadness", "satisfy", "scatter", "scholar",
    "science", "scorpio", "scratch", "seafood", "section", "segment",
    "senator", "serious", "serpent", "service", "session", "setback",
    "setting", "several", "shallow", "shelter", "sheriff", "shuttle",
    "silence", "silicon", "sincere", "skeptic", "slender", "slumber",
    "smaller", "soldier", "somehow", "soprano", "sparked", "speaker",
    "special", "specify", "sponsor", "startup", "station", "stealth",
    "storage", "strange", "subject", "succeed", "success", "suggest",
    "summary", "sunbeam", "sunrise", "support", "supreme", "surface",
    "surgeon", "surplus", "supreme", "survive", "suspect", "suspend",
    "sustain", "synergy", "teacher", "telecom", "tempest", "terrace",
    "theorem", "therapy", "thermal", "thought", "thunder", "tobacco",
    "tonight", "tornado", "tourism", "tourist", "towards", "tracker",
    "trading", "traffic", "tragedy", "trainer", "transit", "travels",
    "therapy", "trigger", "triumph", "trouble", "trusted", "tuition",
    "turbine", "turmoil", "turning", "twitter", "typical", "unaware",
    "undergo", "unicorn", "unified", "uniform", "unknown", "unleash",
    "upright", "utility", "utility", "utopian", "vaccine", "variety",
    "various", "venture", "verdict", "version", "veteran", "vibrant",
    "victory", "village", "vintage", "violent", "viscera", "virtual",
    "visible", "volcano", "voltage", "warrior", "weather", "website",
    "wedding", "weekend", "welcome", "welfare", "western", "whisper",
    "whistle", "winding", "winning", "witness", "woodcut", "workout",
    "yielded",
    # 8-letter common
    "absolute", "abstract", "abundant", "academic", "accepted", "accurate",
    "achieved", "activate", "actively", "actually", "addition", "adequate",
    "adjacent", "adjusted", "advanced", "advocate", "affirmed", "agitated",
    "agreeing", "aircraft", "alliance", "allowing", "although", "altitude",
    "aluminum", "amethyst", "ammonite", "analytic", "announce", "annually",
    "anything", "anywhere", "apparent", "appetite", "applause", "applying",
    "approach", "approval", "approved", "aquarium", "archived", "argument",
    "armchair", "arrested", "artifact", "artistic", "assembly", "assuming",
    "athletic", "attitude", "audience", "aviation", "bachelor", "backdrop",
    "backbone", "backyard", "bacteria", "balanced", "bankrupt", "banknote",
    "baseball", "baseline", "bathroom", "becoming", "beginner", "behavior",
    "believer", "benefits", "betrayal", "birthday", "bleeding", "blessing",
    "blizzard", "blocking", "blossoms", "boldness", "bookmark", "borrowed",
    "botanist", "boundary", "bracelet", "branches", "breaking", "breeding",
    "briefing", "brighten", "bringing", "broadway", "brochure", "building",
    "bulletin", "business", "calendar", "campaign", "canceled", "cannibal",
    "capacity", "cardinal", "carefree", "category", "champion", "changing",
    "chapters", "charcoal", "charging", "charming", "checking", "cheerful",
    "chemical", "children", "choosing", "cinnabar", "circular", "civilian",
    "climbing", "clinical", "clothing", "coaching", "coalesce", "collapse",
    "colonial", "colorful", "combined", "comeback", "comedian", "commence",
    "commerce", "communal", "commuter", "compared", "compiler", "complete",
    "composed", "compound", "computer", "conceive", "conclude", "concrete",
    "condense", "conflict", "confront", "congress", "consider", "constant",
    "consular", "consumer", "contempt", "continue", "contract", "contrary",
    "contrast", "convince", "corridor", "courtesy", "coverage", "cowardly",
    "creative", "credible", "criminal", "critical", "crossing", "crucible",
    "cultural", "currency", "customer", "database", "daughter", "daylight",
    "deadline", "debating", "deciding", "decisive", "declared", "decrease",
    "dedicate", "defender", "defining", "definite", "delicate", "delivery",
    "demanded", "democrat", "demolish", "deodorant","departed", "deployed",
    "designer", "desktops", "detailed", "detector", "devotion", "diabetes",
    "diagnose", "dialogue", "diligent", "dinosaur", "diplomat", "disaster",
    "discount", "discover", "disorder", "dispatch", "displace", "disposal",
    "disprove", "dissolve", "distance", "distinct", "district", "dividend",
    "doctrine", "document", "domestic", "dominant", "dominate", "donation",
    "doubtful", "download", "downsize", "downtown", "dramatic", "drilling",
    "drinking", "dropping", "dumbbell", "duration", "dwelling", "dynamite",
    "earnings", "economic", "educated", "educator", "effected", "efficacy",
    "eighteen", "election", "electric", "elevated", "elevator", "eloquent",
    "embedded", "emission", "emotions", "emphasis", "employed", "employee",
    "emporium", "enclosed", "encoding", "endorsed", "energize", "engaging",
    "engineer", "enormous", "enriched", "enrolled", "ensuring", "entering",
    "entirely", "entitled", "entrance", "envelope", "equality", "equipped",
    "estimate", "eternity", "evaluate", "eventual", "everyone", "evidence",
    "evolving", "examined", "exchange", "exciting", "excluded", "exercise",
    "exhibits", "existent", "expanded", "expedite", "expenses", "explicit",
    "explored", "explorer", "exponent", "extended", "external", "extremes",
    "fabulous", "facility", "factored", "faithful", "familiar", "fantasic",
    "farewell", "fascists", "fastened", "featured", "features", "feedback",
    "feminine", "festival", "figurine", "filename", "filmfare", "finalist",
    "finalize", "finalist", "financed", "finances", "findings", "finished",
    "finisher", "fireclay", "firmness", "flagship", "flashier", "flatware",
    "flexible", "floating", "flourish", "focusing", "followed", "follower",
    "foothold", "footwear", "forecast", "foremost", "forensic", "forestry",
    "formally", "formerly", "fortress", "fountain", "fourteen", "fraction",
    "fragment", "frameset", "freehold", "freeload", "freezing", "frequent",
    "friendly", "frontier", "frostbit", "fruitful", "fullback", "fullness",
    "function", "gambling", "gathered", "gemstone", "generate", "generous",
    "genetics", "geometry", "gladiator","glimpses", "glorious", "glossary",
    "goldfish", "goodness", "gorgeous", "graceful", "gracious", "gradient",
    "graduate", "grandeur", "graphics", "grateful", "gripping", "grudging",
    "guardian", "guidance", "habitual", "hallmark", "handsome", "happened",
    "happiest", "hardware", "harmless", "headband", "headline", "heighten",
    "helpless", "heritage", "highrise", "historic", "holdings", "homeland",
    "homework", "honestly", "honestly", "honoring", "hopeless", "hostname",
    "humanity", "humility", "huntsman", "hurrying", "identify", "ignition",
    "illusion", "imagined", "immature", "imperial", "implicit", "imported",
    "imposing", "imposter", "improper", "improved", "increase", "incurred",
    "indexing", "indirect", "industry", "infantry", "inferior", "infinite",
    "inflated", "informed", "inherent", "inhaling", "initiate", "innocent",
    "innovate", "inspired", "interact", "interest", "interior", "internal",
    "invasion", "invested", "investor", "involved", "isolated", "judgment",
    "junction", "keyboard", "keepsake", "kindling", "kindness", "knockout",
    "labeling", "landmark", "language", "laughter", "lavender", "lifelong",
    "lifetime", "lightest", "lighting", "likeness", "limiting", "linchpin",
    "listener", "literacy", "literary", "literary", "location", "lockdown",
    "majestic", "majority", "makeover", "manifest", "manifold", "marathon",
    "marginal", "markedly", "marriage", "material", "maximize", "measured",
    "mechanic", "mediator", "medicine", "medieval", "membrane", "memorial",
    "merchant", "metadata", "midnight", "military", "minimize", "ministry",
    "minority", "mischief", "moderate", "molecule", "momentum", "monarchy",
    "monetary", "monopoly", "monument", "morality", "mortgage", "movement",
    "multiple", "murmured", "mushroom", "mutually", "mystical", "mythical",
    "narrator", "national", "navigate", "negative", "neighbor", "nitrogen",
    "nobility", "nominate", "nonsense", "notebook", "numerous", "nuisance",
    "obedient", "objected", "obsolete", "obstacle", "obtained", "occupied",
    "occurred", "offering", "official", "offshore", "olympics", "ominates",
    "openness", "operated", "operator", "opponent", "opposing", "opposite",
    "optimism", "optional", "organism", "organize", "oriental", "original",
    "orphaned", "orthodox", "outbreak", "outburst", "outdoors", "outlined",
    "outreach", "outright", "outsider", "overcome", "overhead", "overlook",
    "overseen", "overtime", "overview", "ownwrong", "painting", "pamphlet",
    "pancakes", "paradise", "parallel", "paranoid", "partisan", "passport",
    "patience", "peaceful", "peculiar", "peaceful", "pedigree", "pentagon",
    "perceive", "permeate", "personal", "persuade", "pharmacy", "pheasant",
    "physical", "pilaster", "pipeline", "platform", "playback", "pleasant",
    "pleasure", "plunging", "pointing", "polished", "politely", "politics",
    "polluted", "populace", "portrait", "position", "positive", "possible",
    "possibly", "postpone", "powerful", "practice", "precious", "predator",
    "pregnant", "premiere", "premises", "presence", "preserve", "pressing",
    "prestige", "presumes", "previous", "princely", "princess", "printing",
    "priority", "prisoner", "probably", "proceeds", "producer", "profound",
    "progress", "prohibit", "prolific", "prompted", "properly", "property",
    "proposal", "proposed", "prospect", "prostate", "protocol", "provider",
    "province", "provoked", "prudence", "publicly", "purchase", "pursuing",
    "pursuing", "quantity", "quarters", "question", "radioact", "randomly",
    "reaction", "readable", "readiest", "reckless", "recorder", "recovery",
    "recruits", "redesign", "redirect", "reducing", "reducing", "referral",
    "referred", "reformed", "regional", "register", "regulate", "reinforc",
    "relating", "relating", "relation", "relative", "released", "relevant",
    "reliable", "relieved", "religion", "remained", "remember", "reminded",
    "renowned", "repeated", "replaced", "reported", "reporter", "republic",
    "required", "research", "reserved", "resident", "resigned", "resisted",
    "resolved", "resource", "response", "restless", "restored", "restrict",
    "resulted", "retailer", "retained", "retirees", "retiring", "revealed",
    "reviewer", "revision", "reviving", "rewarded", "ridicule", "rigorous",
    "roadside", "romantic", "roommate", "rotation", "ruthless", "sabotage",
    "sandwich", "scenario", "schedule", "sciences", "scissors", "seasonal",
    "secondly", "sections", "security", "selected", "semester", "sensible",
    "sentence", "separate", "sequence", "sergeant", "sessions", "settling",
    "severity", "shipping", "shocking", "shortage", "shoulder", "shouting",
    "showcase", "shutting", "sideways", "silently", "simulate", "sinister",
    "situated", "skeleton", "skylight", "slippery", "smuggled", "snapshot",
    "snowfall", "socially", "software", "soldiers", "solitary", "solution",
    "somebody", "somewhat", "southern", "spacious", "speaking", "specific",
    "spectrum", "speeding", "spending", "splendid", "sporting", "spotless",
    "squarely", "stagnant", "stagnate", "standard", "standing", "starfish",
    "starting", "starving", "steadily", "steaming", "stepping", "sterling",
    "stimulus", "storming", "straight","strained", "stranger", "strategy",
    "strength", "stressed", "strictly", "striking", "stripped", "strongly",
    "struggle", "stunning", "subjects", "subtract", "suburban", "suddenly",
    "suffered", "suffocal", "suitable", "summoned", "superior", "supplied",
    "supplied", "supplier", "supposed", "suppress", "surgical", "surprise",
    "surround", "survival", "survived", "survivor", "suspense", "symbolic",
    "sympathy", "syndrome", "tactical", "tailored", "takeover", "tangible",
    "tapestry", "taxation", "teamwork", "temporal", "terminal", "terrific",
    "tertiary", "textbook", "thankful", "thirteen", "thorough", "thousand",
    "thriller", "together", "tolerant", "tomorrow", "tortoise", "touching",
    "traction", "training", "transfer", "transmit", "treasure", "treating",
    "trillion", "tropical", "trucking", "truthful", "turnover", "twilight",
    "umbrella", "unbiased", "uncommon", "undercut", "underdog", "underway",
    "unfairly", "unicycle", "universe", "unlikely", "unmarked", "unpacked",
    "unravels", "unstable", "upcoming", "updating", "upmarket", "urbanize",
    "urgently", "utilized", "vacation", "validate", "valuable", "variance",
    "velocity", "ventured", "verbally", "verdicts", "verified", "vertical",
    "veterans", "vicinity", "vigilant", "vineyard", "violates", "violence",
    "virtuoso", "virulent", "visually", "volatile", "voltages", "voluntar",
    "wardrobe", "warranty", "watchful", "waterway", "weakness", "weaponry",
    "welcomed", "whenever", "wherever", "whiskers", "wildcard", "wildlife",
    "windmill", "wireless", "withdraw", "woodwork", "workflow", "workshop",
    "worrying", "yachting", "yearbook", "yearning", "yielding",
}

# Normalize to lowercase
COMMON_WORDS = {w.lower() for w in COMMON_WORDS}

def load_full_dictionary():
    """Load macOS dictionary for fallback word detection."""
    words = set()
    with open("/usr/share/dict/words") as f:
        for line in f:
            w = line.strip().lower()
            if w and w.isalpha():
                words.add(w)
    return words

# ---------------------------------------------------------------------------
# 2. Pronounceability checker
# ---------------------------------------------------------------------------
VOWELS = set("aeiouy")
CONSONANTS = set("bcdfghjklmnpqrstvwxyz")

def is_pronounceable(name):
    """Check if a string looks pronounceable in English."""
    name = name.lower()
    if not name.isalpha():
        return False
    n = len(name)
    if n <= 2:
        return True

    vowel_count = sum(1 for c in name if c in VOWELS)
    if vowel_count == 0:
        return False
    if n >= 4 and vowel_count < n / 4:
        return False

    max_consec_consonants = 0
    consec = 0
    for c in name:
        if c in CONSONANTS:
            consec += 1
            max_consec_consonants = max(max_consec_consonants, consec)
        else:
            consec = 0
    if max_consec_consonants > 3:
        return False

    consec_vowels = 0
    for c in name:
        if c in VOWELS:
            consec_vowels += 1
            if consec_vowels > 3:
                return False
        else:
            consec_vowels = 0

    awkward_bigrams = {
        "qz", "qx", "qk", "qj", "qv", "qw", "qp", "qf", "qg", "qm", "qn",
        "zx", "zq", "zj", "xj", "xq", "xz", "jx", "jz", "jq",
        "bx", "cx", "dx", "fx", "gx", "hx", "jj", "kx", "mx", "px",
        "vx", "wx", "xx", "zz", "bk", "fk", "gq", "kq", "pq", "vq", "wq",
        "bq", "cj", "dq", "fq", "gj", "hq", "jb", "jc", "jd", "jf", "jg",
        "jh", "jk", "jl", "jm", "jn", "jp", "jq", "jr", "js", "jt", "jv",
        "jw", "kb", "kd", "kf", "kg", "kj", "kp", "kq", "kt", "kv", "kw",
        "kz", "lq", "mq", "nq", "pj", "pz", "qb", "qc", "qd", "qe", "qh",
        "qi", "qo", "qq", "qr", "qs", "qt", "qy", "rq", "sq", "tq",
        "vb", "vc", "vd", "vf", "vg", "vh", "vj", "vk", "vm", "vn", "vp",
        "vt", "vw", "vz", "wj", "wv", "wz", "xb", "xc", "xd", "xf", "xg",
        "xh", "xk", "xl", "xm", "xn", "xr", "xs", "xv", "xw",
        "yq", "yj", "yz", "zb", "zd", "zf", "zg", "zk", "zl", "zm",
        "zn", "zp", "zr", "zs", "zt", "zv", "zw",
    }
    for i in range(len(name) - 1):
        if name[i:i+2] in awkward_bigrams:
            return False

    return True


# ---------------------------------------------------------------------------
# 3. Refined value scoring
# ---------------------------------------------------------------------------
def score_domain(name, tld, is_common_word, is_dict_word, category):
    """Score a domain's estimated value/rarity. Higher = better."""
    score = 0
    name_lower = name.lower()
    n = len(name_lower)

    # Base score by length
    length_scores = {1: 10000, 2: 5000, 3: 2000, 4: 800, 5: 400, 6: 200, 7: 100, 8: 50}
    score = length_scores.get(n, 30)

    # TLD multiplier
    tld_mult = {"com": 3.0, "io": 2.0, "ai": 2.5, "co": 1.5, "dev": 1.5, "app": 1.4, "net": 1.3, "org": 1.2}
    score *= tld_mult.get(tld.lower(), 0.8)

    # Word quality multiplier
    if is_common_word:
        score *= 5.0  # Common English word = massive premium
        # Power/brand words get extra
        power_words = {
            "fire", "gold", "star", "moon", "sun", "wave", "storm", "cloud",
            "dream", "flash", "spark", "power", "force", "blade", "swift",
            "brave", "noble", "royal", "crown", "shield", "forge", "trust",
            "prime", "elite", "apex", "titan", "nexus", "vault", "quest",
            "reign", "sage", "epic", "myth", "fate", "core", "pulse", "nova",
            "aura", "zen", "flux", "vibe", "hype", "boost", "surge", "blaze",
            "frost", "shade", "stone", "steel", "iron", "jade", "ruby", "onyx",
            "opal", "pearl", "amber", "ivory", "coral", "eagle", "hawk", "wolf",
            "lion", "tiger", "dragon", "falcon", "raven", "cobra", "viper",
            "byte", "data", "code", "pixel", "cyber", "logic", "sigma", "alpha",
            "omega", "delta", "gamma", "theta", "beta", "trade", "market",
            "stock", "fund", "bank", "coin", "cash", "wealth", "profit",
            "venture", "growth", "yield", "health", "vital", "cure", "heal",
            "pure", "clean", "fresh", "craft", "guild", "lodge", "haven",
            "grove", "crest", "summit", "peak", "harbor", "anchor",
            "ace", "win", "joy", "love", "hope", "grace", "charm", "bold",
            "keen", "true", "wise", "calm", "warm", "free", "fast", "cool",
            "smart", "sharp", "bright", "strong", "solid", "global", "sonic",
            "turbo", "ultra", "hyper", "mega", "super", "rocket", "crystal",
            "diamond", "thunder", "warrior", "phoenix", "legend", "vision",
            "beacon", "bridge", "domain", "motion", "engine", "energy",
            "cosmos", "aurora", "origin", "oracle", "cipher", "matrix",
        }
        if name_lower in power_words:
            score *= 2.0
    elif is_dict_word:
        score *= 2.0  # Obscure dict word — still some value
    elif is_pronounceable(name_lower):
        score *= 1.5  # Brandable pronounceable

    # Category bonuses
    cat_mult = {
        "1char": 5.0,
        "3L_com": 2.5,
        "4L_word_com": 2.0,
        "word_com_5_8": 1.0,
        "3_4L_io": 1.0,
        "3_4L_net_org": 1.0,
    }
    score *= cat_mult.get(category, 1.0)

    return round(score, 1)


# ---------------------------------------------------------------------------
# 4. Main scan
# ---------------------------------------------------------------------------
def main():
    print("Loading dictionaries...")
    full_dict = load_full_dictionary()
    print(f"  System dictionary: {len(full_dict):,} words")
    print(f"  Common words list: {len(COMMON_WORDS):,} words")

    results = {
        "1char": [],
        "3L_com": [],
        "4L_word_com": [],
        "word_com_5_8": [],
        "3_4L_io": [],
        "3_4L_net_org": [],
    }

    print(f"\nScanning {CSV_PATH}...")
    total = 0

    with open(CSV_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            full_domain = row["Domain"].strip()
            tld = row["TLD"].strip().lower()
            drop_date = row.get("Drop Date", "").strip()

            if "." in full_domain:
                name = full_domain.rsplit(".", 1)[0]
                if "." in name:  # skip subdomains
                    continue
            else:
                name = full_domain

            name_lower = name.lower()
            n = len(name_lower)
            is_alpha = name_lower.isalpha()
            is_alnum = name_lower.isalnum()

            is_common = name_lower in COMMON_WORDS
            is_dict = name_lower in full_dict

            # Cat 6: Single character
            if n == 1 and is_alnum:
                s = score_domain(name_lower, tld, is_common, is_dict, "1char")
                results["1char"].append((s, name, tld, drop_date, is_common, is_dict))

            # Cat 1: 3-letter .com (letters only)
            if n == 3 and tld == "com" and is_alpha:
                s = score_domain(name_lower, tld, is_common, is_dict, "3L_com")
                results["3L_com"].append((s, name, tld, drop_date, is_common, is_dict))

            # Cat 2: 4-letter .com real words or pronounceable
            if n == 4 and tld == "com" and is_alpha:
                if is_common or is_dict or is_pronounceable(name_lower):
                    s = score_domain(name_lower, tld, is_common, is_dict, "4L_word_com")
                    results["4L_word_com"].append((s, name, tld, drop_date, is_common, is_dict))

            # Cat 3: Single English word .com (5-8 chars) — COMMON words only
            if 5 <= n <= 8 and tld == "com" and is_alpha:
                if is_common:
                    s = score_domain(name_lower, tld, is_common, is_dict, "word_com_5_8")
                    results["word_com_5_8"].append((s, name, tld, drop_date, True, True))
                elif is_dict:
                    # Include dict words but with lower score
                    s = score_domain(name_lower, tld, False, True, "word_com_5_8")
                    results["word_com_5_8"].append((s, name, tld, drop_date, False, True))

            # Cat 4: 3-4 letter .io
            if 3 <= n <= 4 and tld == "io" and is_alpha:
                s = score_domain(name_lower, tld, is_common, is_dict, "3_4L_io")
                results["3_4L_io"].append((s, name, tld, drop_date, is_common, is_dict))

            # Cat 5: 3-4 letter .net/.org
            if 3 <= n <= 4 and tld in ("net", "org") and is_alpha:
                s = score_domain(name_lower, tld, is_common, is_dict, "3_4L_net_org")
                results["3_4L_net_org"].append((s, name, tld, drop_date, is_common, is_dict))

    print(f"  Scanned {total:,} domains\n")

    # ---------------------------------------------------------------------------
    # 5. Display results per category
    # ---------------------------------------------------------------------------
    for cat, label in [
        ("1char", "SINGLE-CHARACTER DOMAINS (any TLD)"),
        ("3L_com", "3-LETTER .COM DOMAINS (letters only)"),
        ("4L_word_com", "4-LETTER .COM DOMAINS (real words / pronounceable)"),
        ("word_com_5_8", "ENGLISH WORD .COM DOMAINS (5-8 chars)"),
        ("3_4L_io", "3-4 LETTER .IO DOMAINS"),
        ("3_4L_net_org", "3-4 LETTER .NET / .ORG DOMAINS"),
    ]:
        items = sorted(results[cat], key=lambda x: -x[0])
        print(f"{'='*75}")
        print(f"  {label}")
        print(f"  Found: {len(items)} domains")
        print(f"{'='*75}")
        limit = 20 if cat in ("word_com_5_8", "3_4L_net_org") else 30
        for rank, (score, name, tld, drop_date, is_common, is_dict) in enumerate(items[:limit], 1):
            if is_common:
                tag = "COMMON"
            elif is_dict:
                tag = "DICT  "
            elif is_pronounceable(name.lower()):
                tag = "BRAND "
            else:
                tag = "      "
            print(f"  {rank:>3}. {name + '.' + tld:<22}  Score: {score:>9.1f}  [{tag}]  Drop: {drop_date}")
        if not items:
            print("  (none found)")
        print()

    # ---------------------------------------------------------------------------
    # 6. GRAND TOP 30
    # ---------------------------------------------------------------------------
    all_domains = []
    for cat, items in results.items():
        for score, name, tld, drop_date, is_common, is_dict in items:
            all_domains.append((score, name, tld, drop_date, is_common, is_dict, cat))

    all_domains.sort(key=lambda x: -x[0])

    print(f"\n{'#'*75}")
    print(f"  GRAND TOP 30 — MOST VALUABLE PREMIUM DROPPING DOMAINS  (2026-05-14)")
    print(f"{'#'*75}")
    print(f"  {'Rk':<4} {'Domain':<24} {'Score':>10}  {'Type':<7} {'Category':<16} {'Drop'}")
    print(f"  {'--':<4} {'------':<24} {'-----':>10}  {'----':<7} {'--------':<16} {'----'}")

    seen = set()
    rank = 0
    for score, name, tld, drop_date, is_common, is_dict, cat in all_domains:
        key = f"{name.lower()}.{tld}"
        if key in seen:
            continue
        seen.add(key)
        rank += 1
        if rank > 30:
            break
        if is_common:
            tag = "COMMON"
        elif is_dict:
            tag = "DICT"
        elif is_pronounceable(name.lower()):
            tag = "BRAND"
        else:
            tag = "SHORT"
        cat_labels = {
            "1char": "1-char",
            "3L_com": "3L .com",
            "4L_word_com": "4L .com",
            "word_com_5_8": "word .com",
            "3_4L_io": "short .io",
            "3_4L_net_org": "short .net/.org",
        }
        print(f"  {rank:>2}.  {name + '.' + tld:<24} {score:>10.1f}  {tag:<7} {cat_labels.get(cat, cat):<16} {drop_date}")

    # Summary
    print(f"\n{'='*75}")
    print(f"  SUMMARY")
    print(f"{'='*75}")
    for cat, label in [
        ("1char", "Single-character"),
        ("3L_com", "3-letter .com"),
        ("4L_word_com", "4-letter .com (word/pron)"),
        ("word_com_5_8", "Word .com (5-8 char)"),
        ("3_4L_io", "3-4 letter .io"),
        ("3_4L_net_org", "3-4 letter .net/.org"),
    ]:
        total_cat = len(results[cat])
        common_count = sum(1 for x in results[cat] if x[4])
        dict_count = sum(1 for x in results[cat] if x[5] and not x[4])
        print(f"  {label:<30} {total_cat:>5} total  ({common_count} common, {dict_count} dict-only)")
    print(f"  {'TOTAL':<30} {sum(len(v) for v in results.values()):>5}")
    print()


if __name__ == "__main__":
    main()
