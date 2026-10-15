// Friendly names for the routes rails/fake_router.py quotes. The rail id stays on the page as data-rail, and a
// rail with no name here is shown by its id. The Simulated tag comes from the route itself, never from this list.
import { t } from "./i18n.js";

export const RAIL_KEYS = { wise: "rail_wise", sim_pix: "rail_sim_pix", bank_wire: "rail_bank_wire" };

export function railName(rail, lang) {
  return Object.hasOwn(RAIL_KEYS, rail) ? t(lang, RAIL_KEYS[rail]) : rail;
}
