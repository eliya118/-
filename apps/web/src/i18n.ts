import en from "./i18n/en.json";
import he from "./i18n/he.json";

export type Locale = "he" | "en";

const catalogs = { he, en };

export function translate(locale: Locale, key: keyof typeof he): string {
  return catalogs[locale][key];
}
