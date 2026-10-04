/** Typed API client. Types come from the FastAPI OpenAPI schema (`pnpm gen:api`). */
import createFetchClient, { type Middleware } from "openapi-fetch";
import createClient from "openapi-react-query";
import { accessKey } from "./access-key";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type PersonRow = Schemas["PersonRow"];
export type PersonDetail = Schemas["PersonDetail"];
export type Meta = Schemas["Meta"];
export type Overview = Schemas["Overview"];

/** Turn any query error into text for the page: the server's {"error": "..."} body, or a network error. */
export function errorText(e: unknown): string {
  if (e && typeof e === "object" && "error" in e && typeof e.error === "string") return e.error;
  if (e instanceof Error) return e.message;
  return "Something went wrong";
}

const auth: Middleware = {
  onRequest({ request }) {
    if (accessKey) request.headers.set("X-Access-Key", accessKey);
    return request;
  },
};

export const fetchClient = createFetchClient<paths>({ baseUrl: window.location.origin });
fetchClient.use(auth);

/** React Query hooks: $api.useQuery("get", "/api/meta"), etc. */
export const $api = createClient(fetchClient);
