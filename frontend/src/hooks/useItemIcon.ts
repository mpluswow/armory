import { useEffect, useState } from "react";

const FALLBACK_ICON = "https://wow.zamimg.com/images/wow/icons/large/inv_misc_questionmark.jpg";
const CACHE_PREFIX = "icon_";

function getCached(entry: number): string | null {
  try {
    return localStorage.getItem(CACHE_PREFIX + entry);
  } catch {
    return null;
  }
}

function setCache(entry: number, url: string) {
  try {
    localStorage.setItem(CACHE_PREFIX + entry, url);
  } catch {
    // quota exceeded, ignore
  }
}

export function useItemIcon(entry: number | undefined): string {
  const [url, setUrl] = useState<string>(() => {
    if (!entry) return FALLBACK_ICON;
    return getCached(entry) ?? FALLBACK_ICON;
  });

  useEffect(() => {
    if (!entry) return;

    const cached = getCached(entry);
    if (cached) {
      setUrl(cached);
      return;
    }

    let cancelled = false;

    (async () => {
      // Try Wowhead tooltip API first
      try {
        const res = await fetch(
          `https://nether.wowhead.com/tooltip/item/${entry}?dataEnv=1&locale=0`
        );
        if (res.ok) {
          const data = await res.json();
          if (data?.icon) {
            const iconUrl = `https://wow.zamimg.com/images/wow/icons/large/${data.icon}.jpg`;
            if (!cancelled) {
              setCache(entry, iconUrl);
              setUrl(iconUrl);
            }
            return;
          }
        }
      } catch {
        // fall through
      }

      // Fallback: murlocvillage
      const fallbackUrl = `https://wotlk.murlocvillage.com/items/icon_image.php?item=${entry}`;
      if (!cancelled) {
        setCache(entry, fallbackUrl);
        setUrl(fallbackUrl);
      }
    })();

    return () => { cancelled = true; };
  }, [entry]);

  return url;
}
