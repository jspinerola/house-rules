// Harbor Bank demo app (M13): roommate picker, then an account screen polling GET /bank/{id}
// every 2 s. Read-only; no login. Capital One-inspired styling for the Nessie demo.
import { DMSans_400Regular, DMSans_500Medium, DMSans_700Bold, useFonts } from '@expo-google-fonts/dm-sans';
import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { RoommatePicker } from './src/components/RoommatePicker';
import { AccountScreen } from './src/screens/AccountScreen';
import { colors } from './src/theme';

export default function App() {
  const [rid, setRid] = useState<string | null>(null);
  const [fontsLoaded, fontError] = useFonts({ DMSans_400Regular, DMSans_500Medium, DMSans_700Bold });
  if (fontError) console.warn(`[fonts] ${fontError.message}; falling back to system font`);

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.safe} edges={['top']}>
        <StatusBar style="light" />
        {!fontsLoaded && !fontError ? (
          <View style={styles.loading}>
            <ActivityIndicator color="#fff" />
          </View>
        ) : rid ? (
          <AccountScreen rid={rid} onBack={() => setRid(null)} />
        ) : (
          <RoommatePicker onPick={setRid} />
        )}
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.navy },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
