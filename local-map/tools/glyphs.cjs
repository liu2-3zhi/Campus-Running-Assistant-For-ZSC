// Thin Node adapter for the official MapLibre Font Maker WebAssembly API.
const fs = require('node:fs');
const path = require('node:path');
global.fetch = undefined; // Emscripten's Node file reader handles local wasm.
const maker = require('./vendor/sdfglyph.cjs');
maker.onRuntimeInitialized = () => {
  const [fontPath, rangesPath, output] = process.argv.slice(2);
  const font = fs.readFileSync(fontPath);
  const pointer = maker._malloc(font.length);
  maker.HEAPU8.set(font, pointer);
  const stack = maker.ccall('create_fontstack', 'number', ['number'], [0]);
  maker.ccall('fontstack_add_face', null, ['number', 'number', 'number'], [stack, pointer, font.length]);
  fs.mkdirSync(output, { recursive: true });
  for (const start of JSON.parse(fs.readFileSync(rangesPath, 'utf8'))) {
    const destination = path.join(output, `${start}-${start + 255}.pbf`);
    if (fs.existsSync(destination) && fs.statSync(destination).size > 0) continue;
    const glyph = maker.ccall('generate_glyph_buffer', 'number', ['number', 'number'], [stack, start]);
    const data = maker.ccall('glyph_buffer_data', 'number', ['number'], [glyph]);
    const size = maker.ccall('glyph_buffer_size', 'number', ['number'], [glyph]);
    fs.writeFileSync(destination, Buffer.from(maker.HEAPU8.subarray(data, data + size)));
    maker.ccall('free_glyph_buffer', null, ['number'], [glyph]);
  }
  maker.ccall('free_fontstack', null, ['number'], [stack]);
  maker._free(pointer);
};
