// The same record in the W3C Design Tokens Community Group format, which
// Figma's variable import tooling and Style Dictionary both read. It is the
// only honest bridge from the build to Figma: the file is exportable, the
// Figma side is Matt's hands, and figma stays on the study list until then.
import tokens from "../../../../data/design/tokens.json";

type Group = Record<string, unknown>;

function colours(): Group {
  const out: Group = {};
  for (const [name, light] of Object.entries(tokens.colour.light)) {
    out[name] = {
      $type: "color",
      $value: light,
      $extensions: { "com.mattrodenbeck.modes": { light, dark: (tokens.colour.dark as Record<string, string>)[name] } },
      $description: (tokens.colour.roles as Record<string, string>)[name] ?? "",
    };
  }
  for (const [name, value] of Object.entries(tokens.colour.plate)) {
    out[name] = { $type: "color", $value: value, $description: "fixed in both themes" };
  }
  return out;
}

function motion(): Group {
  const out: Group = {};
  for (const m of tokens.motion.tokens) {
    const isDuration = /ms$/.test(m.default);
    const parse = (v: string) => (isDuration ? { value: Number(v.replace("ms", "")), unit: "ms" } : v.startsWith("cubic-bezier") ? v.match(/[\d.]+/g)!.map(Number) : v);
    out[m.name] = {
      $type: isDuration ? "duration" : "cubicBezier",
      $value: parse(m.default),
      $extensions: { "com.mattrodenbeck.modes": { default: parse(m.default), reduced: parse(m.reduced) } },
      $description: `${m.used_by}. ${m.why}`,
    };
  }
  return out;
}

export function GET() {
  const doc = {
    $schema: "https://tr.designtokens.org/format/",
    $description: `Paper and Plate, tokens ${tokens.version}, rendered from data/design/tokens.json. Modes carry the light and dark palettes and the default and reduced motion columns.`,
    colour: colours(),
    grid: Object.fromEntries(Object.entries(tokens.grid).map(([k, v]) => [k, { $type: "dimension", $value: v }])),
    motion: motion(),
  };
  return new Response(JSON.stringify(doc, null, 2), { headers: { "Content-Type": "application/json; charset=utf-8" } });
}
