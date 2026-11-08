import { Platform } from 'react-native';
import Constants from 'expo-constants';
import { useEffect, useRef, useState } from 'react';
import type { BankView } from '../../contracts/types';

const POLL_MS = 2000;
const TIMEOUT_MS = 4000;


// Default: the Metro dev server's own host + /brain (see metro.config.js), which works on
// LAN and over `expo start --tunnel`. EXPO_PUBLIC_BRAIN_URL overrides it.
export function brainBase(): string {
  const direct: unknown = Constants.expoConfig?.extra?.directBrainUrl;
  if (typeof direct === 'string' && direct) return direct.replace(/\/$/, '');
  // Web build: the page is served by the same Metro dev server, so /brain is same-origin.
  if (Platform.OS === 'web' && typeof window !== 'undefined') return `${window.location.origin}/brain`;
  const hostUri = Constants.expoConfig?.hostUri;
  if (!hostUri) return 'http://localhost:8000';
  const host = hostUri.split('/')[0];
  const tunnel = host.endsWith('.exp.direct') || host.endsWith('.on.expo.app') || host.includes('ngrok');
  return `${tunnel ? 'https' : 'http'}://${host}/brain`;
}

export type BankPoll = { view: BankView | null; error: string | null; lastUpdated: Date | null };

export function useBankPoll(rid: string): BankPoll {
  const [state, setState] = useState<BankPoll>({ view: null, error: null, lastUpdated: null });
  const inFlight = useRef(false);

  useEffect(() => {
    let alive = true;
    const url = `${brainBase()}/bank/${rid}`;
    const load = async () => {
      if (inFlight.current) return;
      inFlight.current = true;
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
      try {
        const res = await fetch(url, { signal: ctrl.signal, headers: { 'cache-control': 'no-cache' } });
        if (!res.ok) throw new Error(`GET /bank/${rid} -> ${res.status}`);
        const view = (await res.json()) as BankView;
        if (alive) setState({ view, error: null, lastUpdated: new Date() });
      } catch (e) {
        const msg = ctrl.signal.aborted ? `GET ${url} timed out` : `${(e as Error).message} (${url})`;
        console.warn(`[bank poll] ${msg}`);
        if (alive) setState((s) => ({ ...s, error: msg }));
      } finally {
        clearTimeout(timer);
        inFlight.current = false;
      }
    };
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [rid]);

  return state;
}
