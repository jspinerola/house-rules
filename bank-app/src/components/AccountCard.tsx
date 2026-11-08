import { useEffect, useRef, useState } from 'react';
import { Animated, Easing, StyleSheet, Text, View } from 'react-native';
import { colors, fonts, money } from '../theme';

// Stable fake last-4 per roommate so the card reads like a real account tile.
const last4 = (rid: string) =>
  String([...rid].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 10000, 7)).padStart(4, '0');

function AnimatedBalance({ value }: { value: number }) {
  const [shown, setShown] = useState(value);
  const anim = useRef(new Animated.Value(value)).current;
  const flash = useRef(new Animated.Value(0)).current;
  const prev = useRef(value);
  const [dir, setDir] = useState<'up' | 'down'>('up');

  useEffect(() => {
    const id = anim.addListener(({ value: v }) => setShown(v));
    return () => anim.removeListener(id);
  }, [anim]);

  useEffect(() => {
    if (value === prev.current) return;
    setDir(value > prev.current ? 'up' : 'down');
    prev.current = value;
    Animated.timing(anim, { toValue: value, duration: 800, easing: Easing.out(Easing.cubic), useNativeDriver: false }).start(
      () => setShown(value),
    );
    flash.setValue(1);
    Animated.timing(flash, { toValue: 0, duration: 1600, useNativeDriver: false }).start();
  }, [value, anim, flash]);

  const bg = flash.interpolate({
    inputRange: [0, 1],
    outputRange: ['rgba(0,0,0,0)', dir === 'up' ? 'rgba(30,127,79,0.18)' : 'rgba(200,16,46,0.16)'],
  });

  return (
    <Animated.View style={[styles.balanceWrap, { backgroundColor: bg }]}>
      <Text style={styles.balance} accessibilityLabel={`Available balance ${money(value)}`}>
        {money(Math.round(shown * 100) / 100)}
      </Text>
    </Animated.View>
  );
}

export function AccountCard({ bankName, rid, balance }: { bankName: string; rid: string; balance: number }) {
  return (
    <View style={styles.card}>
      <View style={styles.stripe} />
      <View style={styles.row}>
        <Text style={styles.label}>{bankName} Checking</Text>
        <Text style={styles.mask}>...{last4(rid)}</Text>
      </View>
      <AnimatedBalance value={balance} />
      <Text style={styles.caption}>Available balance</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 18,
    padding: 20,
    paddingTop: 22,
    overflow: 'hidden',
    shadowColor: '#0B2A4A',
    shadowOpacity: 0.14,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 4,
  },
  stripe: { position: 'absolute', top: 0, left: 0, right: 0, height: 4, backgroundColor: colors.red },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  label: { fontFamily: fonts.medium, fontSize: 15, color: colors.ink },
  mask: { fontFamily: fonts.regular, fontSize: 13, color: colors.muted, letterSpacing: 1 },
  balanceWrap: { alignSelf: 'flex-start', borderRadius: 10, marginTop: 14, marginLeft: -6, paddingHorizontal: 6 },
  balance: { fontFamily: fonts.bold, fontSize: 38, color: colors.ink, fontVariant: ['tabular-nums'] },
  caption: { fontFamily: fonts.regular, fontSize: 13, color: colors.muted, marginTop: 2 },
});
