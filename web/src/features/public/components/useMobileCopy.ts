import { useEffect, useState } from "react";

export function useMobileCopy() {
  const [isMobileCopy, setIsMobileCopy] = useState(() => {
    if (typeof window === "undefined" || !("matchMedia" in window)) {
      return false;
    }

    return window.matchMedia("(max-width: 767px)").matches;
  });

  useEffect(() => {
    if (typeof window === "undefined" || !("matchMedia" in window)) {
      return;
    }

    const query = window.matchMedia("(max-width: 767px)");
    const update = () => setIsMobileCopy(query.matches);

    update();
    query.addEventListener("change", update);

    return () => query.removeEventListener("change", update);
  }, []);

  return isMobileCopy;
}
