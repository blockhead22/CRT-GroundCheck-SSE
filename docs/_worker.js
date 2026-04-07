/**
 * Aeteros Research Docs — Basic Auth Middleware
 * Runs as a Cloudflare Pages Worker in front of all static assets.
 * Password is stored as a Pages secret: AUTH_PASSWORD
 * Default fallback (change via: wrangler pages secret put AUTH_PASSWORD)
 */

const REALM = "Aeteros Research";

export default {
  async fetch(request, env) {
    const auth = request.headers.get("Authorization");

    if (!auth || !checkAuth(auth, env)) {
      return new Response("Access restricted.", {
        status: 401,
        headers: {
          "WWW-Authenticate": `Basic realm="${REALM}", charset="UTF-8"`,
          "Content-Type": "text/plain",
          "Cache-Control": "no-store",
        },
      });
    }

    return env.ASSETS.fetch(request);
  },
};

function checkAuth(header, env) {
  try {
    const base64 = header.replace(/^Basic\s+/i, "");
    const decoded = atob(base64);
    const colon = decoded.indexOf(":");
    if (colon === -1) return false;
    const pass = decoded.slice(colon + 1);
    const expected = env.AUTH_PASSWORD ?? "aeteros-2026";
    return pass === expected;
  } catch {
    return false;
  }
}
