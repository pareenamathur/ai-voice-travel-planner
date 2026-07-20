/** UI-side helpers for Supervisor debug panels (no backend logic). */

const AFFIRMATIVE_RE =
  /^\s*(yes|yeah|yep|yup|sure|ok|okay|confirm|confirmed|go\s*ahead)[\s!.,?]*(?:\s+(?:please|thanks|thank\s+you))?[\s!.,?]*$/i;

/** True when the user message looks like an explicit trip confirmation. */
export function looksLikeConfirmation(message: string): boolean {
  return AFFIRMATIVE_RE.test(message.trim());
}

/**
 * Warn when the user affirmed but the backend stayed on confirm
 * (common when speech adds punctuation the server does not accept).
 */
export function shouldShowConfirmRejectedWarning(
  userMessage: string,
  responseIntent: string | null | undefined,
): boolean {
  return looksLikeConfirmation(userMessage) && responseIntent === "confirm";
}
