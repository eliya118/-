import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router";
import { api, type Family } from "./api";
import type { Locale } from "./i18n";
import { translate } from "./i18n";
import { applyLocale, readLocale } from "./locale";
import { ChildrenPage } from "./pages/children";
import { IdeasPage } from "./pages/ideas";
import { WeekPage } from "./pages/week";

export function App() {
  const [locale, setLocale] = useState<Locale>(readLocale);
  useEffect(() => {
    applyLocale(locale);
  }, [locale]);
  const family = useQuery({
    queryKey: ["family"],
    queryFn: () => api<Family>("/api/family"),
    retry: false,
  });
  if (family.isError) {
    return (
      <Routes>
        <Route path="/login" element={<Login locale={locale} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }
  if (family.isLoading || family.data === undefined) {
    return <p className="shell">{translate(locale, "loading")}</p>;
  }
  return (
    <div className="shell">
      <header className="top">
        <h1>{translate(locale, "app")}</h1>
        <nav>
          <NavLink to="/" end>
            {translate(locale, "week")}
          </NavLink>
          <NavLink to="/children">{translate(locale, "children")}</NavLink>
          <NavLink to="/ideas">{translate(locale, "ideas")}</NavLink>
        </nav>
        <div className="row">
          <button
            className="quiet"
            type="button"
            onClick={() => setLocale(locale === "he" ? "en" : "he")}
          >
            {translate(locale, "language")}
          </button>
          <Logout />
        </div>
      </header>
      <Routes>
        <Route path="/" element={<WeekPage locale={locale} family={family.data} />} />
        <Route path="/children" element={<ChildrenPage locale={locale} family={family.data} />} />
        <Route path="/ideas" element={<IdeasPage locale={locale} family={family.data} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

function Logout() {
  const navigate = useNavigate();
  const client = useQueryClient();
  return (
    <button
      className="quiet"
      type="button"
      onClick={() => {
        void api("/api/session", { method: "DELETE" }).finally(() => {
          client.clear();
          navigate("/login");
          window.location.reload();
        });
      }}
    >
      {translate(readLocale(), "logout")}
    </button>
  );
}

function Login({ locale }: { locale: Locale }) {
  const [email, setEmail] = useState("parent@example.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const client = useQueryClient();
  const t = (key: Parameters<typeof translate>[1]) => translate(locale, key);
  return (
    <form
      className="panel login"
      onSubmit={(event) => {
        event.preventDefault();
        setError("");
        void api("/api/session", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        })
          .then(() => client.invalidateQueries({ queryKey: ["family"] }))
          .then(() => window.location.assign("/"))
          .catch(() => setError(t("loginError")));
      }}
    >
      <h1>{t("loginTitle")}</h1>
      <label>
        {t("email")}
        <input value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" />
      </label>
      <label>
        {t("password")}
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
        />
      </label>
      {error ? <p className="error">{error}</p> : null}
      <button type="submit">{t("signIn")}</button>
    </form>
  );
}
