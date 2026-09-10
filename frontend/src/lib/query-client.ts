import {
  QueryClient,
  defaultShouldDehydrateQuery,
  isServer,
} from "@tanstack/react-query";

/**
 * Creates a fresh QueryClient. Called once per request on the server and once
 * per browser session on the client.
 */
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Avoid refetching immediately on the client for data prefetched on the server.
        staleTime: 60 * 1000,
      },
      dehydrate: {
        // Include pending queries in dehydration so streaming/prefetch works.
        shouldDehydrateQuery: (query) =>
          defaultShouldDehydrateQuery(query) ||
          query.state.status === "pending",
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined = undefined;

/**
 * Server: always a new client (prevents cross-request state leaks).
 * Browser: a singleton, reused across renders.
 */
export function getQueryClient() {
  if (isServer) {
    return makeQueryClient();
  }
  if (!browserQueryClient) {
    browserQueryClient = makeQueryClient();
  }
  return browserQueryClient;
}
