require('react-native-gesture-handler/jestSetup');

jest.mock('expo-secure-store', () => {
  let store = {};
  return {
    setItemAsync: jest.fn(async (k, v) => { store[k] = v; }),
    getItemAsync: jest.fn(async (k) => store[k] || null),
    deleteItemAsync: jest.fn(async (k) => { delete store[k]; }),
  };
});

jest.mock('react-native-iap', () => {
  const makeListener = () => ({ remove: jest.fn() });
  return {
    initConnection: jest.fn(async () => true),
    endConnection: jest.fn(async () => true),
    fetchProducts: jest.fn(async () => []),
    requestPurchase: jest.fn(async () => ({})),
    purchaseUpdatedListener: jest.fn(() => makeListener()),
    purchaseErrorListener: jest.fn(() => makeListener()),
    finishTransaction: jest.fn(async () => true),
    getAvailablePurchases: jest.fn(async () => []),
    restorePurchases: jest.fn(async () => []),
    deepLinkToSubscriptions: jest.fn(async () => undefined),
  };
});

jest.mock('react-native/Libraries/EventEmitter/NativeEventEmitter');
