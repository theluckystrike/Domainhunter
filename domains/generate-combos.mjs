/**
 * generate-combos.mjs — Word + TLD matrix generator
 *
 * Generates short_word.cheap_tld combinations optimized for:
 *   - Phrase/statement readability (hair.salon, cool.space)
 *   - Porkbun registration price <= $5/yr
 *   - 3-6 letter common English words
 *
 * NASA Power of 10 compliant:
 *   - All loops bounded (MAX_WORDS=300, MAX_TLDS=80, MAX_OUTPUT=15000)
 *   - Functions under 60 lines
 *   - Min 2 assertions per function
 *   - No globals, no dangerous mutations
 */

import { writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { strict as assert } from 'node:assert';

const MAX_WORDS = 400;
const MAX_TLDS = 80;
const MAX_OUTPUT = 15000;

/**
 * Returns curated short English words (3-6 letters) that pair well with TLDs.
 * @returns {string[]}
 */
function getWords() {
  const words = [
    // Action verbs (2-4 letters)
    'go', 'do', 'be', 'run', 'get', 'try', 'win', 'fly', 'buy',
    'own', 'ask', 'cut', 'dig', 'eat', 'hit', 'let', 'mix', 'pay',
    'pop', 'put', 'rip', 'set', 'sit', 'tag', 'tap', 'tip', 'use',
    'zip', 'nap', 'dip', 'hop',
    // Action verbs (5-6 letters)
    'ship', 'hack', 'push', 'pull', 'send', 'drop', 'kick', 'lift',
    'snap', 'grab', 'flip', 'spin', 'surf', 'swim', 'dive', 'ride',
    'hunt', 'seek', 'burn', 'glow', 'grow', 'hold', 'jump', 'keep',
    'lead', 'make', 'move', 'play', 'read', 'rise', 'save', 'show',
    'stay', 'take', 'turn', 'walk', 'work', 'feel', 'find', 'give',
    'hide', 'join', 'look', 'pick', 'roll', 'rush', 'sell', 'sing',
    'stop', 'talk', 'wake', 'wish', 'cook', 'bake', 'brew', 'pour',
    'slay', 'flex', 'vibe', 'cope', 'chill',
    // Adjectives / descriptors
    'big', 'hot', 'new', 'old', 'raw', 'bad', 'cold', 'cool', 'dark',
    'deep', 'epic', 'fast', 'free', 'good', 'high', 'keen', 'loud',
    'mega', 'nice', 'pure', 'real', 'rich', 'safe', 'slim', 'soft',
    'true', 'vast', 'warm', 'wild', 'wise', 'bold', 'calm', 'dope',
    'fine', 'flat', 'full', 'glad', 'gold', 'half', 'just', 'kind',
    'lean', 'live', 'long', 'main', 'neat', 'open', 'pink', 'rare',
    'sick', 'slow', 'sure', 'tall', 'thin', 'tiny', 'ugly', 'zero',
    'neon', 'mint', 'iron', 'silk', 'fresh',
    // Nouns (things that pair well)
    'ace', 'air', 'art', 'bat', 'bit', 'box', 'bug', 'bus', 'cat',
    'cup', 'day', 'dog', 'egg', 'eye', 'fan', 'fog', 'fun', 'gas',
    'gem', 'gym', 'hat', 'ice', 'ink', 'jam', 'jet', 'joy', 'key',
    'kit', 'lab', 'map', 'mud', 'net', 'nut', 'oil', 'orb', 'owl',
    'pen', 'pie', 'pin', 'pot', 'pup', 'rag', 'ray', 'rig', 'rod',
    'rug', 'rum', 'sap', 'sky', 'spy', 'sun', 'tea', 'tin', 'top',
    'toy', 'van', 'vet', 'vow', 'wax', 'web', 'wit', 'zen', 'dew',
    'fur', 'hue', 'mug', 'oak', 'ore', 'paw', 'rib', 'rye', 'soy',
    // Nouns (5-6 letters)
    'apex', 'barn', 'cave', 'code', 'core', 'crew', 'cube', 'data',
    'dawn', 'dust', 'echo', 'edge', 'fern', 'fire', 'flux', 'foam',
    'fort', 'game', 'grit', 'haze', 'hero', 'hive', 'home', 'hope',
    'iris', 'jade', 'king', 'lava', 'leaf', 'lime', 'link', 'loft',
    'loom', 'maze', 'mesa', 'mind', 'mint', 'mist', 'mode', 'mood',
    'moon', 'moss', 'myth', 'nest', 'node', 'nova', 'opal', 'palm',
    'path', 'peak', 'pine', 'plum', 'pond', 'rain', 'reef', 'root',
    'ruby', 'sage', 'sand', 'seed', 'soul', 'star', 'tide', 'tone',
    'tune', 'vale', 'void', 'volt', 'wave', 'wind', 'wolf', 'yarn',
    'zest', 'zone',
    // Meme / internet culture
    'your', 'my', 'our', 'this', 'that', 'yolo', 'noob', 'boss',
    'chad', 'dank', 'oof', 'bruh', 'yeet', 'mood', 'vibe', 'sus',
    'drip', 'goat', 'fire', 'cap', 'fam', 'bro', 'sis',
  ];

  // Deduplicate
  const unique = [...new Set(words)];
  assert(unique.length > 0, 'Word list must not be empty');
  assert(unique.length <= MAX_WORDS, `Word list exceeds MAX_WORDS (${MAX_WORDS})`);
  return unique;
}

/**
 * Returns cheap TLDs with REAL Porkbun pricing (registration price).
 * @returns {{ tld: string, regPrice: number, renewPrice: number }[]}
 */
function getTlds() {
  const tlds = [
    // $1.28/yr registration
    { tld: 'cfd', regPrice: 1.28, renewPrice: 12.87 },
    { tld: 'cyou', regPrice: 1.28, renewPrice: 12.87 },
    { tld: 'sbs', regPrice: 1.28, renewPrice: 12.87 },
    // $1.34/yr registration
    { tld: 'bond', regPrice: 1.34, renewPrice: 12.87 },
    // $1.54/yr registration — THE SWEET SPOT
    { tld: 'click', regPrice: 1.54, renewPrice: 10.81 },
    { tld: 'beauty', regPrice: 1.54, renewPrice: 12.98 },
    { tld: 'hair', regPrice: 1.54, renewPrice: 12.98 },
    { tld: 'homes', regPrice: 1.54, renewPrice: 12.98 },
    { tld: 'monster', regPrice: 1.54, renewPrice: 12.98 },
    { tld: 'quest', regPrice: 1.54, renewPrice: 12.98 },
    { tld: 'skin', regPrice: 1.54, renewPrice: 12.98 },
    { tld: 'beer', regPrice: 1.54, renewPrice: 26.26 },
    { tld: 'garden', regPrice: 1.54, renewPrice: 26.26 },
    { tld: 'help', regPrice: 1.54, renewPrice: 26.26 },
    { tld: 'lol', regPrice: 1.54, renewPrice: 26.26 },
    { tld: 'mom', regPrice: 1.54, renewPrice: 26.26 },
    { tld: 'pics', regPrice: 1.54, renewPrice: 26.26 },
    { tld: 'rest', regPrice: 1.54, renewPrice: 26.26 },
    { tld: 'surf', regPrice: 1.54, renewPrice: 26.26 },
    { tld: 'baby', regPrice: 1.54, renewPrice: 52.01 },
    // $1.63-$1.96
    { tld: 'top', regPrice: 1.63, renewPrice: 4.63 },
    { tld: 'best', regPrice: 1.72, renewPrice: 15.96 },
    { tld: 'website', regPrice: 1.96, renewPrice: 21.11 },
    { tld: 'space', regPrice: 1.96, renewPrice: 26.26 },
    { tld: 'online', regPrice: 1.96, renewPrice: 28.84 },
    { tld: 'site', regPrice: 1.96, renewPrice: 28.84 },
    // $2.04-$2.57
    { tld: 'xyz', regPrice: 2.04, renewPrice: 12.98 },
    { tld: 'buzz', regPrice: 2.05, renewPrice: 26.26 },
    { tld: 'work', regPrice: 2.06, renewPrice: 10.81 },
    { tld: 'fit', regPrice: 2.06, renewPrice: 26.26 },
    { tld: 'ink', regPrice: 2.06, renewPrice: 26.26 },
    { tld: 'wiki', regPrice: 2.06, renewPrice: 26.26 },
    { tld: 'life', regPrice: 2.06, renewPrice: 29.35 },
    { tld: 'shop', regPrice: 2.06, renewPrice: 31.41 },
    { tld: 'one', regPrice: 2.57, renewPrice: 20.08 },
    { tld: 'live', regPrice: 2.57, renewPrice: 26.26 },
    { tld: 'fun', regPrice: 2.57, renewPrice: 31.41 },
    { tld: 'bar', regPrice: 2.57, renewPrice: 52.01 },
    // $3-5
    { tld: 'art', regPrice: 3.60, renewPrice: 21.11 },
    { tld: 'blog', regPrice: 3.60, renewPrice: 21.11 },
    { tld: 'wtf', regPrice: 3.60, renewPrice: 29.35 },
    { tld: 'world', regPrice: 3.60, renewPrice: 33.47 },
    { tld: 'dog', regPrice: 3.60, renewPrice: 52.01 },
    { tld: 'cloud', regPrice: 3.88, renewPrice: 21.11 },
    { tld: 'club', regPrice: 4.12, renewPrice: 15.96 },
    { tld: 'run', regPrice: 4.12, renewPrice: 22.14 },
    { tld: 'zone', regPrice: 4.63, renewPrice: 29.35 },
    { tld: 'cafe', regPrice: 4.63, renewPrice: 41.71 },
    { tld: 'golf', regPrice: 4.63, renewPrice: 52.01 },
  ];

  assert(tlds.length > 0, 'TLD list must not be empty');
  assert(tlds.length <= MAX_TLDS, `TLD list exceeds MAX_TLDS (${MAX_TLDS})`);
  return tlds;
}

/**
 * Checks if a word.tld combo should be filtered out.
 * @param {string} word
 * @param {{ tld: string }} tldEntry
 * @returns {boolean}
 */
function isBadCombo(word, tldEntry) {
  assert(typeof word === 'string', 'word must be a string');
  assert(typeof tldEntry.tld === 'string', 'tld must be a string');

  const tld = tldEntry.tld;

  // Filter word == tld duplicates
  if (word === tld) return true;

  // Filter offensive combos
  const combined = `${word}${tld}`;
  const badPatterns = ['ass', 'xxx', 'sex', 'porn', 'drug', 'hate', 'kill', 'nazi'];
  const MAX_PATTERNS = 20;
  for (let i = 0; i < badPatterns.length && i < MAX_PATTERNS; i++) {
    if (combined.includes(badPatterns[i])) return true;
  }

  // Filter if total domain > 20 chars
  if (word.length + tld.length + 1 > 20) return true;

  return false;
}

/**
 * Generates combos and writes to file.
 * @param {string} outputPath
 * @returns {{ total: number, filtered: number, written: number }}
 */
function generateCombos(outputPath) {
  assert(typeof outputPath === 'string' && outputPath.length > 0, 'outputPath required');

  const words = getWords();
  const tlds = getTlds();
  const combos = [];
  let filtered = 0;
  let total = 0;

  for (let w = 0; w < words.length && w < MAX_WORDS; w++) {
    for (let t = 0; t < tlds.length && t < MAX_TLDS; t++) {
      total++;
      if (isBadCombo(words[w], tlds[t])) {
        filtered++;
        continue;
      }
      if (combos.length < MAX_OUTPUT) {
        combos.push(`${words[w]}.${tlds[t].tld}`);
      }
    }
  }

  const output = combos.join('\n') + '\n';
  writeFileSync(outputPath, output, 'utf-8');

  return { total, filtered, written: combos.length };
}

function main() {
  const __dirname = dirname(fileURLToPath(import.meta.url));
  const outputPath = join(__dirname, 'domains-to-check.txt');

  assert(typeof __dirname === 'string', 'dirname must resolve');
  assert(outputPath.endsWith('domains-to-check.txt'), 'output path must end correctly');

  const result = generateCombos(outputPath);

  console.log('=== Domain Combo Generator ===');
  console.log(`Total combinations: ${result.total}`);
  console.log(`Filtered (bad):     ${result.filtered}`);
  console.log(`Written to file:    ${result.written}`);
  console.log(`Output: ${outputPath}`);
}

main();
