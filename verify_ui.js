// Runs the browser solver's logic in Node against the real payload and
// checks it agrees with the Python suite.
const fs = require('fs'), zlib = require('zlib');
const html = fs.readFileSync('decryptor.html', 'utf8');
let js = html.split('<script>')[1].split('</script>')[0];
js = js.slice(0, js.indexOf(' * Tile tray'));
js = js.slice(0, js.lastIndexOf('/*'));
js = js.replace(/const PAYLOAD = "[^"]*";/, '').replace('"use strict";', '');

const test = `
const blob0 = ZLIB.gunzipSync(
  Buffer.from(FS.readFileSync('payload.b64', 'utf8').trim(), 'base64')).toString();
const [wordBlob, freqBlob, phraseBlob, synBlob, abbrevBlob] = blob0.split('\\x1e');
const A = "0123456789abcdefghijklmnopqrstuvwxyz";
const freqGroups = freqBlob.split('\\x1d');
let nWords = 0;
wordBlob.split('\\x1d').forEach((group, g) => {
  const cut = group.indexOf('\\n');
  WORD_GROUPS.set(+group.slice(0, cut), group.slice(cut + 1));
  const words = group.slice(cut + 1).split('\\n'), freqs = freqGroups[g];
  for (let i = 0; i < words.length; i++) FREQ.set(words[i], A.indexOf(freqs[i]) / 4);
  nWords += words.length;
});
for (const group of phraseBlob.split('\\x1d')) {
  const cut = group.indexOf('\\n');
  PHRASE_GROUPS.set(+group.slice(0, cut), group.slice(cut + 1));
}
for (const line of (synBlob || '').split('\\n')) {
  if (!line) continue;
  const [w, ...rest] = line.split(' ');
  SYN.set(w, new Set(rest));
}
loadAbbreviations(abbrevBlob);
console.log(\`loaded \${nWords.toLocaleString()} words in \${WORD_GROUPS.size} groups, \${PHRASE_GROUPS.size} phrase groups\`);

const cases = [
  ['on a train, up to its', '10,5', 'saturation point', 0, false],
  ['no more stars', '11', 'astronomers', 0, false],
  ['dirty room', '9', 'dormitory', 0, false],
  ['a rope ends it', '11', 'desperation', 0, false],
  ['voices rant on', '12', 'conversation', 0, false],
  ['out take', '4-3', 'take-out', 0, false],
  ['out take', '4,3', 'take out', 0, false],
  ['the eyes', '4,3', 'they see', 2, true],
  ['point of no return', '5,2,2,6', 'point of no return', 0, false],
];
let fail = 0;
for (const [f, e, want, wantBand, all] of cases) {
  const t0 = Date.now();
  const r = solve(f, parseEnum(e), all);
  const ok = r.length && r[0].text === want && r[0].band === wantBand;
  if (!ok) fail++;
  console.log(\`\${ok ? 'PASS' : 'FAIL'}  \${JSON.stringify(f)} (\${e}) -> \${r.length ? r[0].text : '(none)'} band \${r.length ? r[0].band : '-'}  \${Date.now() - t0}ms\`);
}
const bands = solve('a rope ends it', parseEnum('11'), false).map(a => a.band);
const mono = JSON.stringify(bands) === JSON.stringify([...bands].sort());
console.log(\`\${mono ? 'PASS' : 'FAIL'}  bands monotonic\`);
const esp = solve('a rope ends it', parseEnum('11'), false).find(a => a.text === 'esperantido');
console.log(\`\${esp && esp.band === 1 ? 'PASS' : 'FAIL'}  esperantido banded unranked\`);
if (!mono || !esp || esp.band !== 1) fail++;
// diagnostics parity
const sw = wordSwaps('want top line', parseEnum('11'));
const okSwap = sw.length && sw[0].confident && sw[0].answers[0].text === 'needlepoint';
console.log(\`\${okSwap ? 'PASS' : 'FAIL'}  wordSwaps -> \${sw.length ? sw[0].detail + ' = ' + sw[0].answers[0].text : '(none)'}\`);
const conf = wordSwaps('want top line', parseEnum('11'), 25).filter(s => s.confident);
console.log(\`\${conf.length === 1 ? 'PASS' : 'FAIL'}  exactly one confident swap (\${conf.length})\`);
const nm = letterNearMisses('no more star', parseEnum('11'));
const okNm = nm.some(s => s.answers[0].text === 'astronomers');
console.log(\`\${okNm ? 'PASS' : 'FAIL'}  letterNearMisses finds a dropped letter\`);
const sh = alternativeShapes('on a train, up to its');
const okSh = sh.some(s => s.enumeration === '10,5');
console.log(\`\${okSh ? 'PASS' : 'FAIL'}  alternativeShapes finds 10,5\`);
if (!okSwap || conf.length !== 1 || !okNm || !okSh) fail++;
// synonyms parity — the same expectations test_solver.py holds
const synCases = [
  ['want',  null,   a => a.includes('need') && a.includes('wish'), "want -> need, wish"],
  ['quiet', 'h__h', a => a.length === 1 && a[0] === 'hush',        "quiet + h__h -> hush only"],
  ['quiet', 'h_,_h', a => a.length === 0,                          "pattern carries its enumeration"],
  ['quiet', '_h_h', a => !a.includes('hush'),                      "synonyms match positionally"],
  ['quiet', null,   a => !a.includes('quiet'),                     "a word is not its own synonym"],
  ['',      null,   a => a.length === 0,                           "no word finds nothing"],
  ['zzzzqx', null,  a => a.length === 0,                           "unknown word finds nothing"],
];
for (const [word, pat, ok, label] of synCases) {
  const texts = findSynonyms(word, pat).map(a => a.text);
  const pass = ok(texts);
  if (!pass) fail++;
  console.log(\`\${pass ? 'PASS' : 'FAIL'}  \${label}\${pass ? '' : '  got ' + JSON.stringify(texts.slice(0, 6))}\`);
}
const synBands = findSynonyms('quiet', null);
const synOrdered = JSON.stringify(synBands.map(a => a.band))
  === JSON.stringify([...synBands].sort((a, b) => a.band - b.band || b.score - a.score
                                                 || a.text.localeCompare(b.text)).map(a => a.band));
console.log(\`\${synOrdered ? 'PASS' : 'FAIL'}  synonym bands monotonic\`);
if (!synOrdered) fail++;
const capped = findSynonyms('run', null, 3);
console.log(\`\${capped.length === 3 ? 'PASS' : 'FAIL'}  synonym limit respected\`);
if (capped.length !== 3) fail++;
// abbreviations parity — the same expectations test_solver.py holds
const abbrCases = [
  ['sailor', null, a => JSON.stringify(a) === '["ab","jack","os","tar"]',
   'sailor -> ab, jack, os, tar'],
  ['sailor', '__', a => JSON.stringify(a) === '["ab","os"]', 'sailor + __ -> ab, os'],
  ['Sailor!', null, a => JSON.stringify(a) === '["ab","jack","os","tar"]',
   'lookup ignores case and punctuation'],
  ['archbishop', null, a => a.includes('cantuar'),
   'shorthand is not filtered by the dictionary'],
  ['uncle', null, a => a.includes('pawnbroker'), 'multi-word shorthand survives'],
  ['uncle', '___,___', a => a.length === 0, 'pattern carries its enumeration'],
  ['ab', null, a => a.length === 0, 'a short form is not a clue word'],
  ['zzzzqx', null, a => a.length === 0, 'unknown word has no shorthand'],
  ['', null, a => a.length === 0, 'no word finds nothing'],
];
for (const [word, pat, ok, label] of abbrCases) {
  const texts = findAbbreviations(word, pat).map(a => a.text);
  const pass = ok(texts);
  if (!pass) fail++;
  console.log(\`\${pass ? 'PASS' : 'FAIL'}  \${label}\${pass ? '' : '  got ' + JSON.stringify(texts.slice(0, 6))}\`);
}
const notes = findAbbreviations('note', null);
const byBand = Object.fromEntries(notes.map(a => [a.text, a.band]));
const marks = byBand['do'] === 0 && byBand['a'] === 2;
console.log(\`\${marks ? 'PASS' : 'FAIL'}  source markers survive as bands\`);
const abbrOrdered = JSON.stringify(notes.map(a => a.band))
  === JSON.stringify(notes.map(a => a.band).sort((x, y) => x - y));
console.log(\`\${abbrOrdered ? 'PASS' : 'FAIL'}  shorthand bands monotonic\`);
const unscored = notes.every(a => a.score === 0);
console.log(\`\${unscored ? 'PASS' : 'FAIL'}  shorthand is not scored\`);
const stands = whatItStandsFor('ab');
console.log(\`\${stands.includes('sailor') ? 'PASS' : 'FAIL'}  a short form says what it stands for\`);
if (!marks || !abbrOrdered || !unscored || !stands.includes('sailor')) fail++;
PROC.exit(fail ? 1 : 0);
`;
eval(js + test.replace(/ZLIB/g, 'require("zlib")').replace(/FS/g, 'require("fs")').replace(/PROC/g, 'process'));
