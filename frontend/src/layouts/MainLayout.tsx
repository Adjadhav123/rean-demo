import { ReactNode } from "react";

/**
 * Reserved for a shared page shell (e.g. shared header/sidebar) if this
 * prototype grows beyond its current two pages. Both existing pages
 * currently render their own headers directly, since each has a distinct
 * header layout (Setup vs. Live Inspection banner).
 */
export default function MainLayout({ children }: { children: ReactNode }) {
  return <div style={{ minHeight: "100%" }}>{children}</div>;
}
