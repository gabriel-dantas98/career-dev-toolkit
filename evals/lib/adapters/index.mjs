import { claudeAdapter } from "./claude.mjs";
import { codexAdapter } from "./codex.mjs";
import { cursorAdapter } from "./cursor.mjs";

const adapters = new Map(
  [claudeAdapter, cursorAdapter, codexAdapter].map((adapter) => [
    adapter.id,
    adapter,
  ]),
);

export function getAdapter(id) {
  const adapter = adapters.get(id);
  if (!adapter) throw new TypeError(`unknown provider: ${id}`);
  return adapter;
}
