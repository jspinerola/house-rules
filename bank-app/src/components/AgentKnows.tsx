import { StyleSheet, Text, View } from 'react-native';
import type { Profile } from '../../../contracts/types';
import { colors, fonts, money, shortDate } from '../theme';

const INCOME: Record<Profile['income_pattern'], string> = {
  steady: 'Steady paycheck',
  steady_plus_side: 'Paycheck + side income',
  irregular: 'Irregular income',
};

const STATUS_COLOR = { good: colors.credit, watch: '#B7791F', risk: colors.red } as const;

function Line({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.line}>
      <Text style={styles.label}>{label}</Text>
      <Text style={[styles.value, color ? { color } : null]}>{value}</Text>
    </View>
  );
}

// What this roommate's personal agent has learned (bank history) and been told (their DM). Private.
export function AgentKnows({ profile }: { profile: Profile }) {
  const p = profile.preferences;
  const runway = profile.indicators.runway_days;
  const side = profile.side_income_monthly > 0 ? ` (+${money(profile.side_income_monthly)}/mo side)` : '';
  const told = [
    p.min_buffer != null && `Keep at least ${money(p.min_buffer)} in checking`,
    p.savings_monthly != null && `Saving ${money(p.savings_monthly)}/mo${p.savings_label ? ` for ${p.savings_label}` : ''}`,
    p.front_cap != null && `Front roommates at most ${money(p.front_cap)}`,
    ...p.notes,
  ].filter((x): x is string => Boolean(x));

  return (
    <View style={styles.card}>
      <Line label="Income" value={`${INCOME[profile.income_pattern]}${side}`} />
      {runway && (
        <Line label="Runway" value={`${runway.value} days`} color={STATUS_COLOR[runway.status]} />
      )}
      <Line label="Spending vs usual"
        value={`${profile.spend_trend_pct > 0 ? '+' : ''}${profile.spend_trend_pct}%`} />
      <Text style={styles.sub}>Recurring charges</Text>
      {profile.recurring.length === 0 ? (
        <Text style={styles.muted}>No recurring charges spotted</Text>
      ) : (
        profile.recurring.map((r) => (
          <Line key={r.name} label={`${r.name} · ${shortDate(r.next_date)}`} value={money(-r.amount)} />
        ))
      )}
      <Text style={styles.sub}>You told your agent</Text>
      {told.length === 0 ? (
        <Text style={styles.muted}>Nothing yet. DM your agent things like "keep $300 in checking".</Text>
      ) : (
        told.map((t) => <Text key={t} style={styles.told}>• {t}</Text>)
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 16,
    shadowColor: '#0B2A4A',
    shadowOpacity: 0.08,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  line: { flexDirection: 'row', justifyContent: 'space-between', gap: 12, paddingVertical: 6 },
  label: { flex: 1, fontFamily: fonts.regular, fontSize: 14, color: colors.ink },
  value: { fontFamily: fonts.bold, fontSize: 14, color: colors.ink },
  sub: {
    fontFamily: fonts.medium, fontSize: 12, color: colors.muted, letterSpacing: 0.8,
    textTransform: 'uppercase', marginTop: 14, marginBottom: 2,
  },
  muted: { fontFamily: fonts.regular, fontSize: 13, color: colors.muted, paddingVertical: 4 },
  told: { fontFamily: fonts.regular, fontSize: 14, color: colors.ink, paddingVertical: 3 },
});
