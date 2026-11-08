import { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { BankView } from '../../../contracts/types';
import { AccountCard } from '../components/AccountCard';
import { AgentKnows } from '../components/AgentKnows';
import { TxnRow } from '../components/TxnRow';
import { useBankPoll } from '../brain';
import { colors, fonts } from '../theme';

type Scheduled = BankView['scheduled'][number];
const schedKey = (s: Scheduled) => `${s.date}|${s.description}|${s.amount}`;
const LEAVE_MS = 450;

// Rows first seen after the initial load are "new" and animate in exactly once.
function useNewIds(view: BankView | null) {
  const seen = useRef<Map<string, boolean> | null>(null);
  return useMemo(() => {
    if (!view) return seen.current;
    const first = seen.current === null;
    if (first) seen.current = new Map();
    for (const t of view.transactions) if (!seen.current!.has(t.id)) seen.current!.set(t.id, !first);
    return seen.current;
  }, [view]);
}

// Scheduled items that vanish (executed) linger briefly so they visibly fade out.
function useScheduledWithLeaving(view: BankView | null) {
  const prev = useRef<Scheduled[] | null>(null);
  const leaving = useRef(new Map<string, { item: Scheduled; until: number }>());
  const [, tick] = useState(0);

  const rows = useMemo(() => {
    if (!view) return [];
    const now = Date.now();
    const current = new Set(view.scheduled.map(schedKey));
    if (prev.current) {
      for (const s of prev.current) {
        const k = schedKey(s);
        if (!current.has(k) && !leaving.current.has(k)) leaving.current.set(k, { item: s, until: now + LEAVE_MS });
      }
    }
    prev.current = view.scheduled;
    for (const k of current) leaving.current.delete(k);
    const out = view.scheduled.map((s) => ({ s, key: schedKey(s), leaving: false }));
    for (const [k, v] of leaving.current) out.push({ s: v.item, key: k, leaving: true });
    return out.sort((a, b) => a.s.date.localeCompare(b.s.date));
  }, [view]);

  const hasLeaving = rows.some((r) => r.leaving);
  useEffect(() => {
    if (!hasLeaving) return;
    const t = setTimeout(() => {
      const now = Date.now();
      for (const [k, v] of leaving.current) if (v.until <= now) leaving.current.delete(k);
      tick((n) => n + 1);
    }, LEAVE_MS + 50);
    return () => clearTimeout(t);
  }, [hasLeaving, rows]);

  return rows.filter((r) => !r.leaving || leaving.current.has(r.key));
}

export function AccountScreen({ rid, onBack }: { rid: string; onBack: () => void }) {
  const { view, error, lastUpdated } = useBankPoll(rid);
  const newIds = useNewIds(view);
  const scheduled = useScheduledWithLeaving(view);

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.scroll}>
      <View style={styles.header}>
        <Pressable onPress={onBack} hitSlop={12} accessibilityRole="button" accessibilityLabel="Back to profiles">
          <Text style={styles.back}>{'‹'} Profiles</Text>
        </Pressable>
        <Text style={styles.hello}>Hi, {view?.name ?? rid[0].toUpperCase() + rid.slice(1)}</Text>
      </View>

      <View style={styles.body}>
        {view ? (
          <AccountCard bankName={view.bank_name} rid={rid} balance={view.balance} />
        ) : (
          <View style={[styles.card, styles.placeholder]}>
            <Text style={styles.muted}>{error ? 'Unable to reach the bank' : 'Loading account...'}</Text>
          </View>
        )}

        <View style={styles.status}>
          <View style={[styles.pulse, { backgroundColor: error ? colors.red : colors.credit }]} />
          <Text style={styles.statusText} numberOfLines={2}>
            {error
              ? `Reconnecting... ${error}`
              : lastUpdated
                ? `Updated ${lastUpdated.toLocaleTimeString()}`
                : 'Connecting...'}
          </Text>
        </View>

        {view && (
          <>
            {view.profile && (
              <>
                <Text style={styles.section}>What your agent knows</Text>
                <AgentKnows profile={view.profile} />
              </>
            )}

            <Text style={styles.section}>Scheduled</Text>
            <View style={styles.card}>
              {scheduled.length === 0 ? (
                <Text style={[styles.muted, styles.empty]}>Nothing scheduled</Text>
              ) : (
                scheduled.map((r) => (
                  <TxnRow key={r.key} date={r.s.date} description={r.s.description} amount={r.s.amount} pending
                    leaving={r.leaving} />
                ))
              )}
            </View>

            <Text style={styles.section}>Transactions</Text>
            <View style={styles.card}>
              {view.transactions.length === 0 ? (
                <Text style={[styles.muted, styles.empty]}>No transactions yet</Text>
              ) : (
                view.transactions.map((t) => (
                  <TxnRow key={t.id} date={t.date} description={t.description} amount={t.amount}
                    isNew={newIds?.get(t.id) === true} />
                ))
              )}
            </View>
          </>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.canvas },
  header: { backgroundColor: colors.navy, paddingHorizontal: 20, paddingTop: 14, paddingBottom: 64 },
  back: { fontFamily: fonts.medium, color: '#C9D6E4', fontSize: 15 },
  hello: { fontFamily: fonts.bold, color: '#fff', fontSize: 26, marginTop: 12 },
  scroll: { paddingBottom: 40 },
  body: { paddingHorizontal: 16, marginTop: -48 },
  card: {
    backgroundColor: colors.card,
    borderRadius: 16,
    overflow: 'hidden',
    shadowColor: '#0B2A4A',
    shadowOpacity: 0.08,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  placeholder: { padding: 28, alignItems: 'center' },
  status: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10, paddingHorizontal: 4 },
  pulse: { width: 6, height: 6, borderRadius: 3 },
  statusText: { flex: 1, fontFamily: fonts.regular, fontSize: 11, color: colors.muted },
  section: {
    fontFamily: fonts.bold,
    fontSize: 13,
    color: colors.navy,
    letterSpacing: 1.1,
    textTransform: 'uppercase',
    marginTop: 24,
    marginBottom: 8,
    paddingHorizontal: 4,
  },
  muted: { fontFamily: fonts.regular, color: colors.muted, fontSize: 14 },
  empty: { padding: 18 },
});
