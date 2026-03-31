// Web stub for expo-iap to prevent native module loading on web bundles.
// Provides no-op implementations to avoid runtime errors if inadvertently imported.
module.exports = {
  PurchaseState: {},
  purchaseUpdatedListener: () => ({ remove: () => {} }),
  purchaseErrorListener: () => ({ remove: () => {} }),
  initConnection: async () => false,
  fetchProducts: async () => null,
  getAvailablePurchases: async () => [],
  requestPurchase: async () => null,
  restorePurchases: async () => [],
  finishTransaction: async () => undefined,
  endConnection: () => {},
};
