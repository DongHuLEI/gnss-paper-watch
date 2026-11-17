const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const root = path.resolve(__dirname, '..');

if (process.argv.includes('--help')) {
  console.log('Render source-checked MathML to static SVGs. Daily reading generation needs MathJax; serving and saved-site builds do not.');
  console.log('Install: npm --prefix .cache/math-tools install --no-audit --no-fund --ignore-scripts --package-lock=false mathjax-full@3.2.2');
  console.log('Usage: node scripts/render_equations.cjs [--source one-reading.json] [--output assets-directory]');
  process.exit(0);
}
function argument(name, fallback) {
  const index = process.argv.indexOf(name);
  const target = path.resolve(root, index < 0 ? fallback : process.argv[index + 1]);
  if (!target.startsWith(root + path.sep)) throw new Error('Path must be inside this project');
  return target;
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
const source = argument('--source', 'data/deep_reads');
const output = argument('--output', 'assets/deep-reading');
const files = fs.statSync(source).isDirectory() ? fs.readdirSync(source).filter(name => name.endsWith('.json')).sort().map(name => path.join(source, name)) : [source];
for (const filename of files) {
  const data = JSON.parse(fs.readFileSync(filename, 'utf8'));
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
      if (adaptor.outerHTML(svg).includes('data-mml-node="merror"')) throw new Error('Formula could not be rendered');
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
