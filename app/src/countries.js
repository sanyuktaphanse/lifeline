// The country lists of the onboarding. Every ISO 3166 code a student might name, its flag, and its name in the
// chosen language from the browser's own Intl.DisplayNames, so no country name is copied into the app.

// Source: the `country` field of the entries in rails/knowledge/*.yaml. These are the countries Lifeline has
// sourced entries for, listed first; tests/unit/countries.test.js fails when the knowledge base changes.
export const RULES_ON_FILE = ["BR", "CN", "IN", "SG"];

export const COUNTRIES = (
  "AF AX AL DZ AS AD AO AI AG AR AM AW AU AT AZ BS BH BD BB BY BE BZ BJ BM BT BO BA BW BR VG BN BG BF BI CV KH CM CA KY CF " +
  "TD CL CN CO KM CG CD CK CR CI HR CU CW CY CZ DK DJ DM DO EC EG SV GQ ER EE SZ ET FK FO FJ FI FR GF PF GA GM GE DE GH GI GR " +
  "GL GD GP GU GT GG GN GW GY HT HN HK HU IS IN ID IR IQ IE IM IL IT JM JP JE JO KZ KE KI XK KW KG LA LV LB LS LR LY LI LT LU MO " +
  "MG MW MY MV ML MT MH MQ MR MU YT MX FM MD MC MN ME MS MA MZ MM NA NR NP NL NC NZ NI NE NG NU KP MK MP NO OM PK PW PS PA PG PY " +
  "PE PH PL PT PR QA RE RO RU RW WS SM ST SA SN RS SC SL SG SX SK SI SB SO ZA KR SS ES LK SD SR SE CH SY TW TJ TZ TH TL TG TO TT " +
  "TN TR TM TC TV UG UA AE GB US UY UZ VU VA VE VN WF EH YE ZM ZW"
).split(" ");

// The app's languages as the locales Intl knows them by. Any other language code is passed through as it is.
const LOCALES = { en: "en", pt: "pt-BR", zh: "zh-CN" };
const locale = (lang) => LOCALES[lang] ?? lang ?? "en";

export const hasRules = (code) => RULES_ON_FILE.includes(code);

export function flag(code) {
  return [...code].map((letter) => String.fromCodePoint(0x1f1e6 + letter.charCodeAt(0) - 65)).join("");
}

export function countryName(code, lang) {
  try {
    return new Intl.DisplayNames([locale(lang), "en"], { type: "region" }).of(code) ?? code;
  } catch {
    return code;
  }
}

export function countryGroups(lang) {
  const item = (code) => {
    const name = countryName(code, lang);
    return { code, name, label: `${flag(code)} ${name}` };
  };
  const byName = (a, b) => a.name.localeCompare(b.name, locale(lang));
  return {
    onFile: RULES_ON_FILE.map(item).sort(byName),
    others: COUNTRIES.filter((code) => !hasRules(code)).map(item).sort(byName),
  };
}
