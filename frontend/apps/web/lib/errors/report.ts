/**
 * Report a user-facing error to the backend so the admin Learning page
 * surfaces it in the live feed. Best-effort: any failure to report is
 * swallowed (we never want the act of reporting an error to itself raise
 * a second error and clutter the console).
 *
 * Skips reporting when the error is a SessionExpiredError - that path
 * already shows a dedicated banner on /signin via the chat store flag.
 * Reporting it here would produce a useless "your session expired" row
 * on every reload.
 */
import { SessionExpiredError } from '@/lib/chat/streamChat';

export interface ReportOpts {
  baseUrl: string;
  token: string | null;
  route: string;
  error: unknown;
  /** HTTP status if we have one (chat stream non-2xx). */
  status?: number | null;
  metadata?: Record<string, unknown>;
}

export async function reportError(opts: ReportOpts): Promise<void> {
  if (!opts.token) return;
  if (opts.error instanceof SessionExpiredError) return;

  const message = describeError(opts.error);
  if (!message) return;

  try {
    await fetch(`${opts.baseUrl}/errors`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${opts.token}`,
      },
      body: JSON.stringify({
        route: opts.route,
        message: message.slice(0, 4000),
        status: opts.status ?? null,
        metadata: opts.metadata ?? {},
      }),
      // Use keepalive so a navigation away during the report doesn't
      // cancel the request. Same pattern as analytics beacons.
      keepalive: true,
    });
  } catch {
    // Swallow - reporting must never raise.
  }
}

function describeError(err: unknown): string {
  if (err == null) return '';
  if (err instanceof Error) return err.message || err.name || 'Unknown error';
  if (typeof err === 'string') return err;
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
}
