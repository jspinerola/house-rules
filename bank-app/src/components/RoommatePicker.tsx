import { useEffect, useRef } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, fonts } from '../theme';

export const ROOMMATES = [
  { id: 'alex', name: 'Xander' },
  { id: 'sam', name: 'Julian' },
  { id: 'jordan', name: 'Kevin' },
];

export function RoommatePicker({ onPick }: { onPick: (rid: string) => void }) {
  const anims = useRef(ROOMMATES.map(() => new Animated.Value(0))).current;

  useEffect(() => {
    Animated.stagger(
      90,
      anims.map((a) => Animated.timing(a, { toValue: 1, duration: 420, useNativeDriver: true })),
    ).start();
  }, [anims]);

  return (
    <View style={styles.root}>
      <View style={styles.hero}>
        <Text style={styles.brand}>Harbor Bank</Text>
        <Text style={styles.title}>Choose a profile</Text>
        <Text style={styles.sub}>Pick a roommate to view their accounts.</Text>
      </View>
      <View style={styles.list}>
        {ROOMMATES.map((r, i) => (
          <Animated.View
            key={r.id}
            style={{
              opacity: anims[i],
              transform: [{ translateY: anims[i].interpolate({ inputRange: [0, 1], outputRange: [18, 0] }) }],
            }}
          >
            <Pressable
              onPress={() => onPick(r.id)}
              style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
              accessibilityRole="button"
              accessibilityLabel={`Open ${r.name}'s account`}
            >
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>{r.name[0]}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{r.name}</Text>
                <Text style={styles.meta}>Checking</Text>
              </View>
              <Text style={styles.chevron}>{'›'}</Text>
            </Pressable>
          </Animated.View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.canvas },
  hero: {
    backgroundColor: colors.navy,
    paddingHorizontal: 20,
    paddingTop: 28,
    paddingBottom: 56,
    borderBottomLeftRadius: 28,
    borderBottomRightRadius: 28,
  },
  brand: { fontFamily: fonts.bold, color: '#9FB8D3', fontSize: 13, letterSpacing: 1.6, textTransform: 'uppercase' },
  title: { fontFamily: fonts.bold, color: '#fff', fontSize: 28, marginTop: 10 },
  sub: { fontFamily: fonts.regular, color: '#C9D6E4', fontSize: 14, marginTop: 6, lineHeight: 20 },
  list: { paddingHorizontal: 16, marginTop: -32, gap: 12 },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 16,
    shadowColor: '#0B2A4A',
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  cardPressed: { transform: [{ scale: 0.98 }], opacity: 0.9 },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.navySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { fontFamily: fonts.bold, color: '#fff', fontSize: 18 },
  name: { fontFamily: fonts.bold, fontSize: 18, color: colors.ink },
  meta: { fontFamily: fonts.regular, fontSize: 13, color: colors.muted, marginTop: 2 },
  chevron: { fontFamily: fonts.regular, fontSize: 30, color: colors.red, marginTop: -4 },
});
