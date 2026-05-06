/**
 * Convert a user_id to display handle.
 * - New format `U2026M4X92` → `@U2026M4X92`
 * - Legacy `user_xxxxxx` → `@user_xxxxxx`
 */
export function handleOf(userId) {
  if (!userId) return "";
  return `@${userId}`;
}

/**
 * Append cache-busting param to image URL based on a version string.
 * Avoids stale browser cache when picture is updated.
 */
export function cacheBust(url, version) {
  if (!url) return url;
  const v = encodeURIComponent(version || Date.now());
  return url.includes("?") ? `${url}&v=${v}` : `${url}?v=${v}`;
}
