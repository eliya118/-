import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { applyLocale } from "./locale";
import { WeekGrid } from "./week-grid";
import type { Day } from "./api";
import { sundayOnOrBefore } from "./week";

const days: Day[] = [
  "2025-06-01",
  "2025-06-02",
  "2025-06-03",
  "2025-06-04",
  "2025-06-05",
  "2025-06-06",
  "2025-06-07",
].map((civil, index) => ({
  civil_date: civil,
  hebrew: {
    year: 5785,
    month: "sivan",
    day: 5 + index,
    display_he: `${5 + index} סיון`,
    display_en: `${5 + index} Sivan 5785`,
  },
  shabbat: civil === "2025-06-07",
  holidays: [],
  candle_lighting: null,
  havdalah: null,
}));

describe("week grid", () => {
  it("starts on Sunday and shows the Hebrew date", () => {
    const html = renderToStaticMarkup(
      <WeekGrid days={days} events={[]} locale="he" childNames={{}} />,
    );
    const first = html.indexOf("2025-06-01");
    const last = html.indexOf("2025-06-07");
    expect(first).toBeGreaterThan(-1);
    expect(first).toBeLessThan(last);
    expect(html).toContain("5 סיון");
    expect(sundayOnOrBefore("2025-06-04")).toBe("2025-06-01");
  });

  it("sets rtl when the locale is Hebrew", () => {
    applyLocale("he");
    expect(document.documentElement.lang).toBe("he");
    expect(document.documentElement.dir).toBe("rtl");
    applyLocale("en");
    expect(document.documentElement.dir).toBe("ltr");
  });
});
