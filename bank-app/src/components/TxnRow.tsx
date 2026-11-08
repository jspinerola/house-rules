import { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';
import { colors, fonts, shortDate, signedMoney } from '../theme';

type Props = {
  date: string;
  description: string;
  amount: number;
  isNew?: boolean; // slide in from the right with a short highlight
  leaving?: boolean; // fade and collapse out (scheduled item that just executed)
  pending?: boolean;
};

const ROW_H = 64;

export function TxnRow({ date, description, amount, isNew, leaving, pending }: Props) {
  const enter = useRef(new Animated.Value(isNew ? 0 : 1)).current;
  const glow = useRef(new Animated.Value(isNew ? 1 : 0)).current;
  const exit = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (!isNew) return;
    Animated.spring(enter, { toValue: 1, useNativeDriver: false, friction: 8, tension: 60 }).start();
    Animated.timing(glow, { toValue: 0, duration: 2200, delay: 400, useNativeDriver: false }).start();
  }, [isNew, enter, glow]);

  useEffect(() => {
    if (leaving) Animated.timing(exit, { toValue: 0, duration: 400, useNativeDriver: false }).start();
  }, [leaving, exit]);

  const credit = amount > 0;
  const highlight = glow.interpolate({
    inputRange: [0, 1],
    outputRange: [colors.card, credit ? colors.creditSoft : colors.debitSoft],
  });

  return (
    <Animated.View
      style={[
        styles.row,
        {
          backgroundColor: highlight,
          opacity: Animated.multiply(enter, exit),
          height: exit.interpolate({ inputRange: [0, 1], outputRange: [0, ROW_H] }),
          transform: [{ translateX: enter.interpolate({ inputRange: [0, 1], outputRange: [80, 0] }) }],
        },
      ]}
    >
      <View style={[styles.icon, { backgroundColor: credit ? colors.creditSoft : colors.canvas }]}>
        <Text style={[styles.iconText, { color: credit ? colors.credit : colors.navy }]}>{credit ? '+' : '-'}</Text>
      </View>
      <View style={styles.mid}>
        <Text style={styles.desc} numberOfLines={1}>
          {description}
        </Text>
        <Text style={styles.date}>{pending ? `Scheduled ${shortDate(date)}` : shortDate(date)}</Text>
      </View>
      <Text style={[styles.amount, credit && { color: colors.credit }]}>{signedMoney(amount)}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 16,
    overflow: 'hidden',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.hairline,
  },
  icon: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  iconText: { fontFamily: fonts.bold, fontSize: 18, marginTop: -2 },
  mid: { flex: 1 },
  desc: { fontFamily: fonts.medium, fontSize: 15, color: colors.ink },
  date: { fontFamily: fonts.regular, fontSize: 12, color: colors.muted, marginTop: 2 },
  amount: { fontFamily: fonts.bold, fontSize: 15, color: colors.ink, fontVariant: ['tabular-nums'] },
});
