// https://docs.expo.dev/guides/using-eslint/
const { FlatCompat } = require('@eslint/eslintrc');

// Convert the Expo legacy config into flat config for ESLint v8.
const compat = new FlatCompat({
  baseDirectory: __dirname,
});

module.exports = [
  ...compat.extends('eslint-config-expo'),
  {
    ignores: ['dist/*'],
  },
];
