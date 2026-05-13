import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { getPageMeta } from "../content/publicMeta";

// F2.21.7 — SPA metadata applicator. Reads the current route via
// `useLocation`, looks up the meta entry, and applies document.title
// plus a small set of meta tags through `useEffect`. Browser-safe:
// guards on `typeof document` so native shells, SSR-like test setups,
// or any non-DOM context render this component as a no-op.
//
// The component is split in two so tests can exercise the DOM side
// effects without a Router context:
//   - PublicPageMetaTagSetter — pure-prop renderer that owns useEffect.
//   - PublicPageMeta — Router-aware wrapper used by PublicLayout.

type MetaAttribute = "name" | "property";

function setOrCreateMeta(
  attr: MetaAttribute,
  key: string,
  value: string,
): void {
  if (typeof document === "undefined") return;
  let element = document.head.querySelector<HTMLMetaElement>(
    `meta[${attr}="${key}"]`,
  );
  if (!element) {
    element = document.createElement("meta");
    element.setAttribute(attr, key);
    document.head.appendChild(element);
  }
  element.setAttribute("content", value);
}

interface PublicPageMetaTagSetterProps {
  title: string;
  description: string;
}

export function PublicPageMetaTagSetter({
  title,
  description,
}: PublicPageMetaTagSetterProps) {
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.title = title;
    setOrCreateMeta("name", "description", description);
    setOrCreateMeta("property", "og:title", title);
    setOrCreateMeta("property", "og:description", description);
    setOrCreateMeta("property", "og:type", "website");
  }, [title, description]);

  return null;
}

interface PublicPageMetaProps {
  /**
   * Optional explicit path. When omitted, the current router
   * pathname is used. Useful for tests and edge cases where the
   * router pathname doesn't match the desired metadata entry.
   */
  path?: string;
}

export function PublicPageMeta({ path }: PublicPageMetaProps = {}) {
  const location = useLocation();
  const effectivePath = path ?? location.pathname;
  const meta = getPageMeta(effectivePath);

  return (
    <PublicPageMetaTagSetter
      title={meta.title}
      description={meta.description}
    />
  );
}

export default PublicPageMeta;
