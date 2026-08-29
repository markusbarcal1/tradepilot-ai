import assert from "node:assert/strict";
import fs from "node:fs/promises";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";


process.env.VITE_API_BASE_URL = "http://api.test";
process.env.VITE_SUPABASE_URL = "https://project.supabase.co";
process.env.VITE_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_test";

globalThis.localStorage = {
  getItem: () => null,
  setItem: () => {},
  removeItem: () => {},
};

const vite = await createServer({
  server: { middlewareMode: true },
  appType: "custom",
  logLevel: "error",
});

try {
  const { supabase } = await vite.ssrLoadModule("/src/lib/supabase.js");
  const apiModule = await vite.ssrLoadModule("/src/api/client.js");
  const { default: AuthContext } = await vite.ssrLoadModule(
    "/src/auth/AuthContext.js"
  );
  const { default: AuthGate } = await vite.ssrLoadModule(
    "/src/components/AuthGate.jsx"
  );
  const { default: Login } = await vite.ssrLoadModule(
    "/src/components/Login.jsx"
  );
  const { default: InviteSetup } = await vite.ssrLoadModule(
    "/src/components/InviteSetup.jsx"
  );

  let accessToken = "first-access-token";
  supabase.auth.getSession = async () => ({
    data: { session: { access_token: accessToken } },
    error: null,
  });

  const requests = [];
  apiModule.api.defaults.adapter = async (config) => {
    requests.push(config);
    return {
      data: {},
      status: 200,
      statusText: "OK",
      headers: {},
      config,
    };
  };

  await apiModule.analyzeTicker("AAPL", "1y", "1d");
  accessToken = "refreshed-access-token";
  await apiModule.getAuthenticatedUser();
  assert.equal(requests[0].headers.Authorization, "Bearer first-access-token");
  assert.equal(requests[1].headers.Authorization, "Bearer refreshed-access-token");

  let streamRequest = null;
  globalThis.fetch = async (url, options) => {
    streamRequest = { url, options };
    return new Response(
      'event: complete\ndata: {"results":[],"scanned_count":0}\n\n',
      { status: 200, headers: { "content-type": "text/event-stream" } }
    );
  };
  const streamResult = await apiModule.streamScanMarket("1y", "1d");
  assert.deepEqual(streamResult.results, []);
  assert.equal(
    streamRequest.options.headers.Authorization,
    "Bearer refreshed-access-token"
  );
  assert.doesNotMatch(streamRequest.url, /token|jwt|refreshed-access-token/i);

  const loginMarkup = renderToStaticMarkup(
    React.createElement(
      AuthContext.Provider,
      { value: { signIn: async () => ({ error: null }) } },
      React.createElement(Login)
    )
  );
  assert.match(loginMarkup, /Private Beta/);
  assert.match(loginMarkup, /Sign In/);
  assert.doesNotMatch(loginMarkup, /Sign Up|Create Account|Register/);

  const inviteMarkup = renderToStaticMarkup(
    React.createElement(
      AuthContext.Provider,
      { value: { completeInvite: async () => ({ error: null }), signOut: async () => {} } },
      React.createElement(InviteSetup)
    )
  );
  assert.match(inviteMarkup, /Set your password/);
  assert.match(inviteMarkup, /Complete invitation/);
  assert.doesNotMatch(inviteMarkup, /Sign Up|Create Account|Register/);

  const forbiddenMarkup = renderToStaticMarkup(
    React.createElement(
      AuthContext.Provider,
      {
        value: {
          status: "forbidden",
          currentUser: null,
          signOut: async () => {},
        },
      },
      React.createElement(AuthGate)
    )
  );
  assert.match(forbiddenMarkup, /does not currently have access/);
  assert.match(forbiddenMarkup, /Sign Out/);

  const appSource = await fs.readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
  const scannerSource = await fs.readFile(
    new URL("../src/components/ScannerPanel.jsx", import.meta.url),
    "utf8"
  );
  const authSource = await fs.readFile(
    new URL("../src/auth/AuthProvider.jsx", import.meta.url),
    "utf8"
  );
  assert.doesNotMatch(scannerSource, /localStorage/);
  assert.doesNotMatch(authSource, /signUp|console\.log\(.*session|access_token.*localStorage/);
  assert.match(authSource, /updateUser\(\{ password \}\)/);
  assert.match(appSource, /localStorage\.setItem\(THEME_STORAGE_KEY/);
  assert.doesNotMatch(appSource, /localStorage\.setItem\("tradepilot-watchlist"/);
  assert.match(appSource, /analysisRequestRef\.current\.controller\?\.abort/);

  const gateSource = await fs.readFile(
    new URL("../src/components/AuthGate.jsx", import.meta.url),
    "utf8"
  );
  assert.match(gateSource, /key=\{currentUser\.user_id\}/);

  console.log("Frontend authentication flow tests passed.");
} finally {
  await vite.close();
}
