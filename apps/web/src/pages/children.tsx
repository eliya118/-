import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Family } from "../api";
import type { Locale } from "../i18n";
import { translate } from "../i18n";

type Row = { id?: string; display_name: string; birth_year: number; birth_month: number };

export function ChildrenPage({ locale, family }: { locale: Locale; family: Family }) {
  const t = (key: Parameters<typeof translate>[1]) => translate(locale, key);
  const client = useQueryClient();
  const [rows, setRows] = useState<Row[]>(
    family.children.map((child) => ({
      id: child.id,
      display_name: child.display_name,
      birth_year: child.birth_year,
      birth_month: child.birth_month,
    })),
  );
  const [error, setError] = useState("");
  return (
    <form
      className="panel"
      onSubmit={(event) => {
        event.preventDefault();
        setError("");
        void api("/api/children", {
          method: "PUT",
          body: JSON.stringify({ children: rows }),
        })
          .then(() => client.invalidateQueries({ queryKey: ["family"] }))
          .catch((reason: Error) => setError(reason.message));
      }}
    >
      <div className="card-list">
        {rows.map((row, index) => (
          <div className="row" key={row.id ?? `new-${index}`}>
            <label>
              {t("childName")}
              <input
                value={row.display_name}
                onChange={(event) => update(index, { display_name: event.target.value })}
                required
              />
            </label>
            <label>
              {t("birthYear")}
              <input
                type="number"
                value={row.birth_year}
                onChange={(event) => update(index, { birth_year: Number(event.target.value) })}
                required
              />
            </label>
            <label>
              {t("birthMonth")}
              <input
                type="number"
                min={1}
                max={12}
                value={row.birth_month}
                onChange={(event) => update(index, { birth_month: Number(event.target.value) })}
                required
              />
            </label>
            <button
              className="quiet"
              type="button"
              onClick={() => setRows(rows.filter((_, item) => item !== index))}
            >
              {t("remove")}
            </button>
          </div>
        ))}
      </div>
      {error ? <p className="error">{error}</p> : null}
      <div className="row">
        <button
          className="quiet"
          type="button"
          onClick={() => setRows([...rows, { display_name: "", birth_year: 2018, birth_month: 6 }])}
        >
          {t("addChild")}
        </button>
        <button type="submit">{t("saveChildren")}</button>
      </div>
    </form>
  );

  function update(index: number, patch: Partial<Row>) {
    setRows(rows.map((row, item) => (item === index ? { ...row, ...patch } : row)));
  }
}
