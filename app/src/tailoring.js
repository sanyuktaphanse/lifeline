// The few places the app follows the trip the student gave in the onboarding. Without a trip each says it plainly.
import { t } from "./i18n.js";
import { countryName } from "./countries.js";

export function greeting(trip, lang) {
  return trip?.study ? t(lang, "hello_study", { place: countryName(trip.study, lang) }) : t(lang, "hello_plain");
}

export function fromHome(trip, lang) {
  return trip?.home ? t(lang, "from_home", { place: countryName(trip.home, lang) }) : t(lang, "from_home_plain");
}

// One chat starter about money from home. China, India and Brazil have their own, because rails/knowledge has
// entries on money from those countries; any other home asks the general question.
const OWN_STARTER = { CN: "starter_home_cn", IN: "starter_home_in", BR: "starter_home_br" };

export function homeStarter(trip, lang) {
  if (!trip?.home) return null;
  return t(lang, OWN_STARTER[trip.home] ?? "starter_home_other", { place: countryName(trip.home, lang) });
}

// The /precheck kinds that fit the trip. Each is one rails/fake_router.py answers (docs/api.md, POST /precheck), and
// each call writes to the ledger, so the Me page makes one only when the student taps its button.
export function precheckFor(trip) {
  const checks = [];
  if (trip?.home === "CN") checks.push({ action_kind: "remit_from_china", provider: "cn_bank_remit_sim" });
  if (trip?.study === "CN") checks.push({ action_kind: "arrive_in_china", provider: "alipay" });
  if (trip?.study === "BR") checks.push({ action_kind: "enable_pix", provider: "sim_pix" });
  return checks;
}
