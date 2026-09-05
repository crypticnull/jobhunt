// The record, served verbatim, so anyone can check the page against the file
// it was rendered from.
import tokens from "../../../../data/design/tokens.json";

export function GET() {
  return new Response(JSON.stringify(tokens, null, 2), { headers: { "Content-Type": "application/json; charset=utf-8" } });
}
