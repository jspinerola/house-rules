// Extends app.json. By default the app calls the brain through the Metro dev server's
// /brain proxy (metro.config.js, target BRAIN_URL). EXPO_PUBLIC_BRAIN_URL makes the phone
// call the brain directly instead.
module.exports = ({ config }) => ({
  ...config,
  extra: {
    ...config.extra,
    // Omitted when unset: the manifest serializes null as {}.
    ...(process.env.EXPO_PUBLIC_BRAIN_URL ? { directBrainUrl: process.env.EXPO_PUBLIC_BRAIN_URL } : {}),
  },
});
