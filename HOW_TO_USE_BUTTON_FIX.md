# How To Use Button Fix

## Problem

The "How To Use" button on the route results screen (`route.tsx`) and home screen (`index.tsx`) appeared to do nothing when tapped on native Android.

**Root cause:** `frontend/app/how-to-use.tsx` contained a bare `<iframe>` JSX element used to embed the YouTube tutorial video. `<iframe>` is a web-only HTML element — React Native has no corresponding native view. When the screen mounted on Android, React Native threw a runtime error on the `<iframe>`, the screen crashed, and the navigation stack reverted to the calling screen. The tap appeared to produce no effect.

The button code and navigation call in both `index.tsx` and `route.tsx` were always correct (`router.push('/how-to-use')`). The screen registration in `_layout.tsx` was always correct. The bug was entirely inside `how-to-use.tsx`.

---

## Files Changed

| File | Change |
|---|---|
| `frontend/app/how-to-use.tsx` | Added `Platform`, `Linking` imports; guarded `<iframe>` for web; added YouTube button for native |

No other files changed. `index.tsx`, `route.tsx`, `billingGuards.ts`, `_layout.tsx`, all billing/auth/subscription files — untouched.

---

## What Changed

### 1. Imports

```diff
 import { 
   View, 
   Text, 
   StyleSheet, 
   TouchableOpacity, 
   ScrollView, 
-  Dimensions 
+  Dimensions,
+  Platform,
+  Linking,
 } from 'react-native';
```

### 2. Video block — Platform-conditional render

```diff
         <View style={styles.howtoVideoWrapper}>
-          <iframe
-            src="https://www.youtube.com/embed/fS-wJRoVlzc?rel=0"
-            title="RouteCast Tutorial"
-            frameBorder="0"
-            loading="lazy"
-            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
-            allowFullScreen
-            style={styles.howtoVideoIframe as any}
-          />
+          {Platform.OS === 'web' ? (
+            <iframe
+              src="https://www.youtube.com/embed/fS-wJRoVlzc?rel=0"
+              title="RouteCast Tutorial"
+              frameBorder="0"
+              loading="lazy"
+              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
+              allowFullScreen
+              style={styles.howtoVideoIframe as any}
+            />
+          ) : (
+            <TouchableOpacity
+              style={styles.watchVideoBtn}
+              onPress={() => Linking.openURL('https://www.youtube.com/watch?v=fS-wJRoVlzc')}
+              activeOpacity={0.8}
+            >
+              <Ionicons name="logo-youtube" size={28} color="#ef4444" />
+              <Text style={styles.watchVideoText}>Watch Tutorial on YouTube</Text>
+            </TouchableOpacity>
+          )}
         </View>
```

### 3. New styles

```typescript
watchVideoBtn: {
  flexDirection: 'row',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 10,
  backgroundColor: '#1a1a1a',
  borderRadius: 10,
  paddingVertical: 18,
  paddingHorizontal: 20,
  borderWidth: 1,
  borderColor: '#ef444440',
},
watchVideoText: {
  color: '#fff',
  fontSize: 15,
  fontWeight: '600',
},
```

---

## Behavior After Fix

| Platform | Behavior |
|---|---|
| Android / iOS (native) | Tapping "How To Use" navigates to the guide screen. The tutorial video section shows a red YouTube button. Tapping it opens `youtube.com/watch?v=fS-wJRoVlzc` in the device browser. |
| Web | Unchanged — embedded `<iframe>` plays inline as before. |

---

## Deployment

| Item | Status |
|---|---|
| New Android build required | **Yes** — frontend JS change |
| Backend change required | No |
| Render deploy required | No |
| Files with billing/auth/subscription logic changed | None |

---

## Notes

- The `<iframe>` crash was silent — no visible error dialog for the user, just an instant revert of navigation.
- Both entry points (`index.tsx` line ~1295, `route.tsx` line ~722) use identical `router.push('/how-to-use')` — no changes needed there.
- The screen has no paywall or auth checks; it is accessible to any authenticated user.
