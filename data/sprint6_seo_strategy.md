# Sprint 6 - SEO Strategy: Internal Linking & Cross-Site Architecture

## Overview

Three complementary domains targeting a combined 2.4M monthly search volume across food/recipe and image editing verticals.

| Domain | Vertical | Total Monthly SV |
|--------|----------|-----------------|
| ingredientcalculator.com | Cooking/Baking | 333K |
| pictureeditor.net | Image Editing | 1,300K |
| recipetool.net | Nutrition/Meal Planning | 746K |

---

## 1. Cross-Site Linking Plan

### Strategy
Link between sites only where contextual relevance exists (recipe<->ingredients, recipe<->nutrition). Do NOT cross-link pictureeditor.net to cooking sites (no topical relevance = dilutes authority).

### Approved Cross-Links

| From | To | Anchor Text | Context |
|------|----|-------------|---------|
| ingredientcalculator.com (index) | recipetool.net | "Plan your weekly meals" | CTA in footer/sidebar |
| ingredientcalculator.com/recipe-converter.html | recipetool.net/calorie-calculator.html | "Calculate calories for your converted recipe" | End-of-content CTA |
| ingredientcalculator.com/serving-size-calculator.html | recipetool.net/meal-planner.html | "Plan meals with proper portions" | Contextual body link |
| recipetool.net (index) | ingredientcalculator.com | "Convert ingredient measurements" | Tool recommendation section |
| recipetool.net/calorie-calculator.html | ingredientcalculator.com/cups-to-grams.html | "Convert cups to grams for accurate tracking" | Contextual body link |
| recipetool.net/meal-planner.html | ingredientcalculator.com/serving-size-calculator.html | "Adjust serving sizes" | Contextual body link |

### NOT Linking (by design)
- pictureeditor.net does NOT link to cooking sites (zero topical overlap)
- Cooking sites do NOT link to pictureeditor.net
- This preserves topical authority signals for each domain cluster

---

## 2. Internal Linking Structure (Within Each Site)

### ingredientcalculator.com (Hub & Spoke Model)

```
                    [Homepage - Hub]
                   /    |    |    \     \
    [cups-to-grams] [egg-sub] [converter] [ratios] [serving-size]
         |              |          |          |           |
         └──────────────┼──────────┼──────────┘           |
                        └──────────┴──────────────────────┘
```

| From Page | Links To | Anchor Text |
|-----------|----------|-------------|
| Homepage | cups-to-grams.html | "Cups to Grams Converter" |
| Homepage | egg-substitute.html | "Egg Substitute Calculator" |
| Homepage | recipe-converter.html | "Recipe Unit Converter" |
| Homepage | baking-ratios.html | "Baking Ratio Calculator" |
| Homepage | serving-size-calculator.html | "Serving Size Calculator" |
| cups-to-grams.html | recipe-converter.html | "Convert other recipe units" |
| cups-to-grams.html | baking-ratios.html | "Common baking ratios" |
| egg-substitute.html | baking-ratios.html | "Baking ratio reference" |
| egg-substitute.html | recipe-converter.html | "Scale your recipe" |
| recipe-converter.html | cups-to-grams.html | "Cups to grams reference" |
| recipe-converter.html | serving-size-calculator.html | "Adjust serving sizes" |
| baking-ratios.html | cups-to-grams.html | "Convert measurements" |
| baking-ratios.html | egg-substitute.html | "Find egg substitutes" |
| serving-size-calculator.html | recipe-converter.html | "Convert full recipes" |
| serving-size-calculator.html | cups-to-grams.html | "Measurement conversions" |

### pictureeditor.net (Hub & Spoke Model)

```
              [Homepage - Hub]
             /    |    |    \
    [compress] [crop] [convert] [remove-bg]
         |        |       |          |
         └────────┼───────┘          |
                  └──────────────────┘
```

| From Page | Links To | Anchor Text |
|-----------|----------|-------------|
| Homepage | compress.html | "Compress Images" |
| Homepage | crop.html | "Crop Images" |
| Homepage | convert.html | "Convert Image Format" |
| Homepage | remove-background.html | "Remove Background" |
| compress.html | convert.html | "Convert to a smaller format" |
| compress.html | crop.html | "Crop before compressing" |
| crop.html | compress.html | "Compress your cropped image" |
| crop.html | remove-background.html | "Remove background instead" |
| convert.html | compress.html | "Compress after converting" |
| convert.html | remove-background.html | "Remove background from PNG" |
| remove-background.html | convert.html | "Convert to PNG for transparency" |
| remove-background.html | crop.html | "Crop your image first" |

### recipetool.net (Hub & Spoke Model)

```
        [Homepage - Hub]
        /              \
[meal-planner]  [calorie-calculator]
       |                |
       └────────────────┘
```

| From Page | Links To | Anchor Text |
|-----------|----------|-------------|
| Homepage | meal-planner.html | "Weekly Meal Planner" |
| Homepage | calorie-calculator.html | "Calorie Calculator" |
| meal-planner.html | calorie-calculator.html | "Track calories for your meal plan" |
| calorie-calculator.html | meal-planner.html | "Plan meals within your calorie budget" |

---

## 3. Anchor Text Strategy

### Principles
1. **Primary anchors**: Use exact-match keyword for homepage links (from nav/footer)
2. **Contextual anchors**: Use long-tail/natural variations for in-content links
3. **Diversity**: No single anchor text used more than 3x across the network
4. **No over-optimization**: Mix branded, exact-match, and natural anchors at ~30/40/30 ratio

### Keyword-to-Anchor Mapping

| Target Page | Primary Keyword | Anchor Variations |
|-------------|----------------|-------------------|
| /cups-to-grams.html | cups to grams | "cups to grams converter", "convert cups to grams", "measurement converter" |
| /egg-substitute.html | egg substitute | "egg substitute calculator", "egg replacements", "find egg alternatives" |
| /recipe-converter.html | recipe converter | "convert recipe units", "recipe unit converter", "scale recipes" |
| /baking-ratios.html | baking ratios | "baking ratio calculator", "common baking ratios", "baking proportions" |
| /serving-size-calculator.html | serving size calculator | "adjust serving sizes", "portion calculator", "serving size tool" |
| /compress.html | compress image | "compress images online", "image compressor", "reduce image size" |
| /crop.html | crop image | "crop images online", "image cropper", "crop photos" |
| /convert.html | convert image / png to jpg | "convert image format", "png to jpg converter", "image format converter" |
| /remove-background.html | remove background | "remove image background", "background remover", "transparent background" |
| /calorie-calculator.html | calorie calculator | "calculate calories", "food calorie counter", "calorie tracking tool" |
| /meal-planner.html | meal planner | "plan weekly meals", "meal planning tool", "weekly meal planner" |

---

## 4. Content Silo Structure

### Silo 1: Cooking & Baking (ingredientcalculator.com)
- **Pillar**: Homepage (ingredient calculator)
- **Cluster**: All subpages are measurement/conversion tools
- **Topical authority**: Baking, cooking, ingredient measurement
- **Supporting entities**: Units (cups, grams, ml, oz), ingredients, recipes

### Silo 2: Image Editing (pictureeditor.net)
- **Pillar**: Homepage (general picture editor)
- **Cluster**: Specific image operations (compress, crop, convert, remove-bg)
- **Topical authority**: Online image editing, file conversion, photo tools
- **Supporting entities**: File formats (PNG, JPG, WebP), image dimensions, compression

### Silo 3: Nutrition & Meal Planning (recipetool.net)
- **Pillar**: Homepage (recipe nutrition calculator)
- **Cluster**: Calorie tracking, meal planning
- **Topical authority**: Nutrition, calorie counting, diet planning
- **Supporting entities**: Macros, calories, food groups, meal schedules

---

## 5. Traffic Potential by Page

| Page | Monthly Search Volume | Competition | Expected CTR | Est. Monthly Traffic (Position 5-10) |
|------|----------------------|-------------|--------------|--------------------------------------|
| convert.html (png-to-jpg etc) | 550,000 | High | 3-5% | 16,500-27,500 |
| calorie-calculator.html | 673,000 | High | 2-4% | 13,460-26,920 |
| remove-background.html | 450,000 | High | 3-5% | 13,500-22,500 |
| cups-to-grams.html | 201,000 | Medium | 5-8% | 10,050-16,080 |
| compress.html | 165,000 | Medium | 4-7% | 6,600-11,550 |
| crop.html | 135,000 | Medium | 4-7% | 5,400-9,450 |
| egg-substitute.html | 90,000 | Medium | 5-8% | 4,500-7,200 |
| recipetool.net homepage | 40,000 | Medium | 5-8% | 2,000-3,200 |
| meal-planner.html | 33,000 | Medium | 4-6% | 1,320-1,980 |
| recipe-converter.html | 22,000 | Low | 6-10% | 1,320-2,200 |
| serving-size-calculator.html | 12,000 | Low | 6-10% | 720-1,200 |
| baking-ratios.html | 8,000 | Low | 8-12% | 640-960 |

### Total Addressable Traffic
- **Target search volume**: ~2,379,000/month
- **Conservative estimate (position 8-10)**: ~75,000 visits/month
- **Optimistic estimate (position 4-6)**: ~130,000 visits/month
- **Breakout scenario (position 1-3 on low-comp)**: ~200,000 visits/month

---

## 6. Implementation Priority

### Phase 1 (Immediate - Sprint 6)
1. Ensure all pages have proper internal links (nav + in-content)
2. Submit sitemaps to GSC (DONE)
3. Enable Web Analytics for traffic monitoring (BLOCKED - needs token with RUM write permission)

### Phase 2 (Sprint 7)
1. Cross-link between ingredientcalculator.com and recipetool.net
2. Add structured data (HowTo, FAQTool) to each page
3. Monitor indexing status and troubleshoot any crawl errors

### Phase 3 (Sprint 8+)
1. Build external backlinks to high-value pages (convert, calorie-calculator, remove-background)
2. Add blog/content sections for long-tail keyword capture
3. Optimize based on actual traffic data from Web Analytics
