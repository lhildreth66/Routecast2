const path = require('path');
const createExpoWebpackConfigAsync = require('@expo/webpack-config');

module.exports = async function (env, argv) {
  const config = await createExpoWebpackConfigAsync(env, argv);
  config.resolve = config.resolve || {};
  config.resolve.alias = config.resolve.alias || {};
  // Force expo-iap to a safe web stub so no native module loads in web bundles.
  config.resolve.alias['expo-iap'] = path.resolve(__dirname, 'web/expo-iap-web-stub.js');
  return config;
};
