/**
 * Central demo state: settings the operator controls, plus readiness derived from
 * them by the backend.
 *
 * Settings live here rather than in each page so the Run page, the settings panel
 * and the Architecture page all agree on the current configuration.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ApiError, api } from '../api/client';
import type {
  Bootstrap,
  Readiness,
  SettingsPayload,
} from '../api/types';

interface DemoState {
  loading: boolean;
  loadError: string | null;
  bootstrap: Bootstrap | null;
  settings: SettingsPayload | null;
  readiness: Readiness | null;
  readinessPending: boolean;
  updateSettings: (patch: Partial<SettingsPayload>) => void;
}

/** Debounce so typing in the Gateway URL box does not fire a request per keystroke. */
const READINESS_DEBOUNCE_MS = 400;

export function useDemoState(): DemoState {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [readinessPending, setReadinessPending] = useState(false);

  // Load defaults from the server's .env once.
  useEffect(() => {
    const controller = new AbortController();
    api
      .bootstrap(controller.signal)
      .then((data) => {
        setBootstrap(data);
        setSettings({
          modelId: data.settings.modelId,
          gatewayUrl: data.settings.gatewayUrl,
          maxResults: data.settings.maxResults,
          domainInclude: data.settings.domainInclude,
          domainExclude: data.settings.domainExclude,
          publishedFrom: data.settings.publishedFrom,
          publishedTo: data.settings.publishedTo,
        });
        setLoadError(null);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setLoadError(
          error instanceof ApiError ? error.message : String(error),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  // Re-derive readiness whenever settings change, debounced and cancellable so a
  // slow in-flight check never overwrites a newer one.
  const settingsKey = useMemo(
    () => (settings ? JSON.stringify(settings) : ''),
    [settings],
  );
  const latestRequest = useRef(0);

  useEffect(() => {
    if (!settings) return;
    const requestId = ++latestRequest.current;
    const controller = new AbortController();
    setReadinessPending(true);

    const timer = window.setTimeout(() => {
      api
        .readiness(settings, controller.signal)
        .then((data) => {
          if (requestId === latestRequest.current) setReadiness(data);
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted) return;
          if (requestId === latestRequest.current) {
            setLoadError(error instanceof ApiError ? error.message : String(error));
          }
        })
        .finally(() => {
          if (requestId === latestRequest.current) setReadinessPending(false);
        });
    }, READINESS_DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
    // Deliberately keyed on settingsKey rather than on `settings`: the object is
    // recreated on every render, which would re-run this effect continuously.
    // settingsKey changes only when a value the backend cares about changes.
  }, [settingsKey]);

  const updateSettings = useCallback((patch: Partial<SettingsPayload>) => {
    setSettings((current) => (current ? { ...current, ...patch } : current));
  }, []);

  return {
    loading,
    loadError,
    bootstrap,
    settings,
    readiness,
    readinessPending,
    updateSettings,
  };
}
