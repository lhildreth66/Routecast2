import AsyncStorage from '@react-native-async-storage/async-storage';
import { Alert } from 'react-native';

// Reusable entitlement check for Boondocking Pro
// Reads a single AsyncStorage boolean key: entitlements.boondockingPro
// Defaults to false if absent or invalid
export async function hasBoondockingPro(): Promise<boolean> {
  try {
    const raw = await AsyncStorage.getItem('entitlements.boondockingPro');
    if (!raw) return false;
    // Accept boolean strings or JSON booleans
    if (raw === 'true') return true;
    if (raw === 'false') return false;
    try {
      const parsed = JSON.parse(raw);
      return !!parsed;
    } catch {
      // Fallback: any truthy non-empty string considered true? No, be strict.
      return false;
    }
  } catch {
    return false;
  }
}

// Dev-only: Toggle Pro entitlement (guarded by __DEV__)
export async function devToggleProEntitlement(): Promise<void> {
  if (!__DEV__) {
    return; // Silently ignore in production
  }
  try {
    const current = await hasBoondockingPro();
    const next = !current;
    await AsyncStorage.setItem('entitlements.boondockingPro', next ? 'true' : 'false');
    Alert.alert(
      'Dev: Pro Entitlement',
      `Pro entitlement ${next ? 'enabled' : 'disabled'} (dev build only)`
    );
  } catch (err) {
    Alert.alert('Error', 'Failed to toggle entitlement');
  }
}
