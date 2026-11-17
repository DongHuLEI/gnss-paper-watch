const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const root = path.resolve(__dirname, '..');

if (process.argv.includes('--help')) {
  console.log('Regenerate committed formula SVGs from data/deep_reads/*.json. Daily Python builds use these assets without Node or MathJax.');
  console.log('Install the generation-only dependency: npm --prefix .cache/math-tools install --no-audit --no-fund --ignore-scripts --package-lock=false mathjax-full@3.2.2');
  console.log('Then run: node scripts/render_equations.cjs');
  process.exit(0);
}
function library(name) {
  const location = path.join(root, '.cache', 'math-tools', 'node_modules', 'mathjax-full', name);
  if (!fs.existsSync(location)) throw new Error('Formula generator not installed. Run node scripts/render_equations.cjs --help for setup.');
  return require(location);
}
const {mathjax} = library('js/mathjax.js');
const {MathML} = library('js/input/mathml.js');
const {SVG} = library('js/output/svg.js');
const {liteAdaptor} = library('js/adaptors/liteAdaptor.js');
const {RegisterHTMLHandler} = library('js/handlers/html.js');
const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
const doc = mathjax.document('', {InputJax: new MathML(), OutputJax: new SVG({fontCache: 'none'})});
const source = path.join(root, 'data', 'deep_reads');
const output = path.join(root, 'assets', 'deep-reading');
for (const filename of fs.readdirSync(source).filter(name => name.endsWith('.json')).sort()) {
  const data = JSON.parse(fs.readFileSync(path.join(source, filename), 'utf8'));
  if (!/^\d{4}\.\d{4,5}$/.test(data.paper_id)) throw new Error('Invalid paper ID');
  const directory = path.join(output, data.paper_id);
  fs.mkdirSync(directory, {recursive: true});
  for (const equation of data.equations) {
    if (!/^eq-[a-z-]+$/.test(equation.id)) throw new Error('Invalid equation ID');
    for (const field of ['mathml', 'mathml_second']) {
      if (!equation[field]) continue;
      const math = equation[field];
      const digest = crypto.createHash('sha256').update(math).digest('hex').slice(0, 12);
      const node = doc.convert('<math xmlns="http://www.w3.org/1998/Math/MathML">' + math + '</math>', {display: true});
      const svg = adaptor.firstChild(node);
      const viewbox = adaptor.getAttribute(svg, 'viewBox').split(/\s+/).map(Number);
      adaptor.setAttribute(svg, 'width', String(Math.ceil(viewbox[2] * 0.020)));
      adaptor.setAttribute(svg, 'height', String(Math.ceil(viewbox[3] * 0.020)));
      adaptor.setAttribute(svg, 'color', '#20303b');
      adaptor.removeAttribute(svg, 'style');
      const target = equation.id + '-' + digest + '.svg';
      fs.writeFileSync(path.join(directory, target), adaptor.outerHTML(svg) + '\n');
      console.log(path.relative(root, path.join(directory, target)));
    }
  }
}
fs.copyFileSync(path.join(root, '.cache', 'math-tools', 'node_modules', 'mathjax-full', 'LICENSE'), path.join(output, 'LICENSE.txt'));
