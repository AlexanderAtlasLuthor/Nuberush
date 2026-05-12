import type { CapacitorConfig } from '@capacitor/cli';

// F2.0: Lovable preview URL and Lovable-namespaced appId removed.
// `appId` is a placeholder reverse-domain string; replace with the real
// production identifier before publishing to App Store / Play Store.
const config: CapacitorConfig = {
  appId: 'com.nuberush.app',
  appName: 'NubeRush',
  webDir: 'dist',
};

export default config;
