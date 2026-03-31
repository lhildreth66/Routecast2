// Learn more https://docs.expo.io/guides/customizing-metro
const path = require('path');
const { getDefaultConfig } = require('expo/metro-config');
const { resolve } = require('metro-resolver');

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

const defaultResolveRequest = config.resolver.resolveRequest;

// On web, alias expo-iap to a safe stub so the web bundle never loads native billing.
config.resolver.resolveRequest = (context, moduleName, platform) => {
	if (platform === 'web' && moduleName === 'expo-iap') {
		return {
			type: 'sourceFile',
			filePath: path.resolve(__dirname, 'web/expo-iap-web-stub.js'),
		};
	}
	if (defaultResolveRequest) return defaultResolveRequest(context, moduleName, platform);
	return resolve(context, moduleName, platform);
};

module.exports = config;
