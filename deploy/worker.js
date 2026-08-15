function withHeaders(response, pathname) {
  const headers = new Headers(response.headers);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  if (pathname.startsWith("/assets/") || pathname.startsWith("/graph/")) {
    headers.set("Cache-Control", "public, max-age=3600");
  } else {
    headers.set("Cache-Control", "public, max-age=300");
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function fetchAsset(env, request, pathname) {
  const url = new URL(request.url);
  url.pathname = pathname;
  url.search = "";
  return env.ASSETS.fetch(new Request(url, request));
}

async function fetchFirstAsset(env, request, pathname) {
  const candidates = [pathname, `/dist${pathname}`];
  for (const candidate of candidates) {
    const response = await fetchAsset(env, request, candidate);
    if (response.status !== 404) return response;
  }
  return fetchAsset(env, request, pathname);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    let pathname = decodeURIComponent(url.pathname);

    if (pathname === "/") {
      pathname = "/index.html";
    }

    let response = await fetchFirstAsset(env, request, pathname);
    if (response.status === 404 && !pathname.split("/").pop().includes(".")) {
      response = await fetchFirstAsset(env, request, `${pathname.replace(/\/$/, "")}/index.html`);
    }

    return withHeaders(response, pathname);
  },
};
