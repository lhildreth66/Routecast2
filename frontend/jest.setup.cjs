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
  return {
    initConnection: jest.fn(async () => true),
    endConnection: jest.fn(async () => true),
    getSubscriptions: jest.fn(async () => []),
    requestSubscription: jest.fn(async () => ({})),
    purchaseUpdatedListener: jest.fn(() => ({ remove: jest.fn() })),
    purchaseErrorListener: jest.fn(() => ({ remove: jest.fn() })),
    finishTransaction: jest.fn(async () => true),
    getAvailablePurchases: jest.fn(async () => []),
  };
});

jest.mock('react-native/Libraries/EventEmitter/NativeEventEmitter');
