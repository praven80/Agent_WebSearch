/**
 * Hash-based navigation.
 *
 * The app has three pages, so a router dependency is not worth its weight -- or,
 * as it turned out, its advisories. The hash keeps deep links and the browser
 * back button working.
 */

import { useEffect, useState } from 'react';

const PAGES = ['run', 'architecture', 'comparison'] as const;
export type PageId = (typeof PAGES)[number];

const DEFAULT_PAGE: PageId = 'run';

export const PAGE_TITLES: Record<PageId, string> = {
  run: 'Run the comparison',
  architecture: 'Architecture',
  comparison: 'Side by side',
};

function parseHash(): PageId {
  const raw = window.location.hash.replace(/^#\/?/, '').split('?')[0];
  return (PAGES as readonly string[]).includes(raw) ? (raw as PageId) : DEFAULT_PAGE;
}

/** Current page, kept in sync with the URL hash in both directions. */
export function useHashPage(): [PageId, (page: PageId) => void] {
  const [page, setPage] = useState<PageId>(parseHash);

  useEffect(() => {
    const onHashChange = () => setPage(parseHash());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const navigate = (next: PageId) => {
    if (next !== page) {
      window.location.hash = `#/${next}`;
    }
  };

  return [page, navigate];
}
