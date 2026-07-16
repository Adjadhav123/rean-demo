const STORAGE_KEY = "vq-expected-texts";

export interface ExpectedTextMatch {
  expectedText: string;
  status: "matched" | "missing" | "pending";
  detectedText?: string | null;
}

export function normalizeText(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "")
    .trim();
}

export function parseExpectedTexts(input: string): string[] {
  const values = input
    .split(/[\n,;]+/g)
    .map((value) => value.trim())
    .filter(Boolean);

  const seen = new Set<string>();
  const uniqueValues: string[] = [];

  for (const value of values) {
    const normalized = normalizeText(value);
    if (!normalized || seen.has(normalized)) {
      continue;
    }

    seen.add(normalized);
    uniqueValues.push(value);
  }

  return uniqueValues;
}

export function loadExpectedTexts(): string[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.filter((item): item is string => typeof item === "string");
  } catch {
    return [];
  }
}

export function saveExpectedTexts(values: string[]): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(values));
}

export function clearExpectedTexts(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(STORAGE_KEY);
}

export function matchExpectedTexts(
  expectedTexts: string[],
  detectedTexts: string[],
  active: boolean,
): ExpectedTextMatch[] {
  if (!expectedTexts.length) {
    return [];
  }

  if (!active) {
    return expectedTexts.map((expectedText) => ({
      expectedText,
      status: "pending" as const,
      detectedText: null,
    }));
  }

  const normalizedDetected = detectedTexts
    .map((text) => ({
      raw: text,
      normalized: normalizeText(text),
    }))
    .filter((item) => item.normalized.length > 0);

  return expectedTexts.map((expectedText) => {
    const normalizedExpected = normalizeText(expectedText);
    const matched = normalizedDetected.find((detected) => {
      return (
        detected.normalized === normalizedExpected ||
        detected.normalized.includes(normalizedExpected) ||
        normalizedExpected.includes(detected.normalized)
      );
    });

    return {
      expectedText,
      status: matched ? "matched" : "missing",
      detectedText: matched?.raw ?? null,
    };
  });
}
