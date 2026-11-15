import type { Locale } from "./i18n";

const KEY = "kc_locale";

export function readLocale(): Locale {
  const stored = localStorage.getItem(KEY);
  return stored === "en" ? "en" : "he";
}

export function applyLocale(locale: Locale): void {
  document.documentElement.lang = locale;
  document.documentElement.dir = locale === "he" ? "rtl" : "ltr";
  localStorage.setItem(KEY, locale);
}
