/** Access key: taken from ?key= in the link, remembered in this browser and sent on every API call.
 * It also stays in the address bar (the router keeps the `key` search param), so refreshes and bookmarks
 * work even when the browser blocks the server's cookie. Same behaviour as the first viewer. */
import { storage } from "@/lib/storage";

const fromUrl = new URLSearchParams(window.location.search).get("key");
if (fromUrl) storage.set("ts.key", fromUrl);

export const accessKey: string = fromUrl ?? storage.get<string>("ts.key", "");

/** Append the key to a URL for links the browser follows itself (e.g. CSV downloads). */
export function withKey(url: string): string {
  if (!accessKey) return url;
  return `${url}${url.includes("?") ? "&" : "?"}key=${encodeURIComponent(accessKey)}`;
}
