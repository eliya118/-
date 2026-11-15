import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Family, type Ideas } from "../api";
import type { Locale } from "../i18n";
import { translate } from "../i18n";

export function IdeasPage({ locale, family }: { locale: Locale; family: Family }) {
  const t = (key: Parameters<typeof translate>[1]) => translate(locale, key);
  const [childId, setChildId] = useState(family.children[0]?.id ?? "");
  const activities = useQuery({
    queryKey: ["activities", childId],
    queryFn: () => api<Ideas>(`/api/ideas/activities?child_id=${childId}`),
    enabled: Boolean(childId),
  });
  const breakfast = useQuery({
    queryKey: ["meals", "breakfast", childId],
    queryFn: () => api<Ideas>(`/api/ideas/meals?slot=breakfast&child_id=${childId}`),
    enabled: Boolean(childId),
  });
  const dinner = useQuery({
    queryKey: ["meals", "dinner", childId],
    queryFn: () => api<Ideas>(`/api/ideas/meals?slot=dinner&child_id=${childId}`),
    enabled: Boolean(childId),
  });
  return (
    <section className="panel">
      <label>
        {t("whichChild")}
        <select value={childId} onChange={(event) => setChildId(event.target.value)}>
          {family.children.map((child) => (
            <option key={child.id} value={child.id}>
              {child.display_name} ({child.age_band})
            </option>
          ))}
        </select>
      </label>
      {family.children.length === 0 ? <p>{t("addChild")}</p> : null}
      <IdeaList title={t("activities")} data={activities.data} empty={t("degraded")} />
      <IdeaList title={t("breakfast")} data={breakfast.data} empty={t("degraded")} />
      <IdeaList title={t("dinner")} data={dinner.data} empty={t("degraded")} />
    </section>
  );
}

function IdeaList({ title, data, empty }: { title: string; data: Ideas | undefined; empty: string }) {
  return (
    <div>
      <h2>{title}</h2>
      {data?.degraded ? <p className="error">{empty}</p> : null}
      <div className="card-list">
        {data?.items.map((item) => (
          <article key={item.id}>{item.text}</article>
        ))}
      </div>
    </div>
  );
}
