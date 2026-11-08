// Harbor Bank demo app (P0, plain): roommate picker, then an account screen polling
// GET /bank/{id} every 2 s. Styling lands in D5. Read-only; no login.
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { BankView } from '../contracts/types';

// On a phone, set EXPO_PUBLIC_BRAIN_URL to the laptop's LAN or tunnel URL.
const BRAIN_URL = process.env.EXPO_PUBLIC_BRAIN_URL ?? 'http://localhost:8000';
const ROOMMATES = [
  { id: 'alex', name: 'Alex' },
  { id: 'sam', name: 'Sam' },
  { id: 'jordan', name: 'Jordan' },
];

const money = (n: number) => `${n < 0 ? '-' : ''}$${Math.abs(n).toFixed(2)}`;

function Banner() {
  return (
    <View style={styles.banner}>
      <Text style={styles.bannerText}>Demo: Nessie sandbox data. Not financial advice.</Text>
    </View>
  );
}

function Account({ rid, onBack }: { rid: string; onBack: () => void }) {
  const [view, setView] = useState<BankView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch(`${BRAIN_URL}/bank/${rid}`);
        if (!res.ok) throw new Error(`GET /bank/${rid} -> ${res.status}`);
        const data = (await res.json()) as BankView;
        if (alive) {
          setView(data);
          setError(null);
        }
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
    };
    load();
    const id = setInterval(load, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [rid]);

  return (
    <ScrollView contentContainerStyle={styles.body}>
      <Pressable onPress={onBack}>
        <Text style={styles.link}>{'< Accounts'}</Text>
      </Pressable>
      {error && <Text style={styles.error}>{error}</Text>}
      {!view ? (
        <Text>Loading...</Text>
      ) : (
        <>
          <Text style={styles.small}>{view.bank_name} - {view.name}'s checking</Text>
          <Text style={styles.balance}>{money(view.balance)}</Text>
          <Text style={styles.h2}>Scheduled</Text>
          {view.scheduled.length === 0 && <Text style={styles.small}>Nothing scheduled</Text>}
          {view.scheduled.map((s, i) => (
            <View key={i} style={styles.row}>
              <Text>{s.date} {s.description}</Text>
              <Text>{money(s.amount)}</Text>
            </View>
          ))}
          <Text style={styles.h2}>Transactions</Text>
          {view.transactions.map((t) => (
            <View key={t.id} style={styles.row}>
              <Text style={styles.desc}>{t.date} {t.description}</Text>
              <Text>{money(t.amount)}</Text>
            </View>
          ))}
        </>
      )}
    </ScrollView>
  );
}

export default function App() {
  const [rid, setRid] = useState<string | null>(null);
  return (
    <View style={styles.container}>
      <Banner />
      {rid ? (
        <Account rid={rid} onBack={() => setRid(null)} />
      ) : (
        <View style={styles.body}>
          <Text style={styles.h1}>Who are you?</Text>
          {ROOMMATES.map((r) => (
            <Pressable key={r.id} style={styles.pick} onPress={() => setRid(r.id)}>
              <Text style={styles.pickText}>{r.name}</Text>
            </Pressable>
          ))}
        </View>
      )}
      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff', paddingTop: 48 },
  banner: { backgroundColor: '#fff3cd', padding: 8 },
  bannerText: { textAlign: 'center', fontSize: 12 },
  body: { padding: 16, gap: 8 },
  h1: { fontSize: 22, fontWeight: '600' },
  h2: { fontSize: 16, fontWeight: '600', marginTop: 16 },
  balance: { fontSize: 32, fontWeight: '700' },
  small: { color: '#555' },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  desc: { flexShrink: 1, marginRight: 8 },
  pick: { padding: 16, borderWidth: 1, borderColor: '#ccc', borderRadius: 8 },
  pickText: { fontSize: 18 },
  link: { color: '#0a58ca' },
  error: { color: 'crimson' },
});
