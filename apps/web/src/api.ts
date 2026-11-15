export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    headers.set("X-KC-Request", "1");
  }
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  if (response.status === 204) {
    return undefined as T;
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body?.error?.message ?? "Request failed";
    throw new ApiError(message, response.status);
  }
  return body as T;
}

export type Child = {
  id: string;
  display_name: string;
  birth_year: number;
  birth_month: number;
  age_years: number;
  age_band: string;
};

export type Family = {
  id: string;
  timezone: string;
  locale: string;
  children: Child[];
};

export type Holiday = { kind: string; name_he: string; name_en: string };

export type Day = {
  civil_date: string;
  hebrew: {
    year: number;
    month: string;
    day: number;
    display_he: string;
    display_en: string;
  };
  shabbat: boolean;
  holidays: Holiday[];
  candle_lighting: string | null;
  havdalah: string | null;
};

export type CalEvent = {
  id: string;
  title: string;
  starts_at: string;
  ends_at: string | null;
  all_day: boolean;
  remind_at: string | null;
  generation: number;
  locale: string;
  child_ids: string[];
  civil_date: string;
};

export type Week = { sunday: string; days: Day[]; events: CalEvent[] };

export type Draft = {
  title: string;
  child_ids: string[];
  starts_at: string;
  ends_at: string | null;
  all_day: boolean;
  remind_at: string | null;
};

export type Preview = {
  status: "ready" | "needs_clarification";
  draft: Draft | null;
  questions: string[];
};

export type Ideas = {
  items: { id: string; text: string }[];
  source: string;
  degraded?: boolean;
};
