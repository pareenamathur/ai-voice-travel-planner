export type LoadingHint =
  | "plan"
  | "recommend"
  | "edit"
  | "explain"
  | "confirm"
  | "clarify"
  | "export"
  | "default";

const RECOMMEND_RE =
  /\b(suggest|recommend|recommendation|best\s+.+\s+places?|caf[eé]s?|nightlife|local\s+markets?|shopping\s+places?|food\s+places?)\b/i;
const EDIT_RE =
  /\b(add|include|replace|remove|move|change|swap|edit|insert|drop|skip)\b/i;
const EXPLAIN_RE =
  /\b(why|how|what|when|tell me|explain|describe|about)\b/i;
const ADVISORY_RE =
  /\b(doable|feasible|kid[- ]?friendly|wheelchair|senior|elderly|safe|scam|monsoon|pack(?:ing)?|expensive|budget|transport|taxi|hectic|walking|suitable)\b/i;
const PLAN_RE = /\b(plan|itinerary|trip|days?\s+in|weekend|generate)\b/i;
const CONFIRM_RE =
  /^\s*(yes|yeah|yep|sure|ok|okay|confirm|go\s*ahead|proceed|generate(\s+it)?|looks?\s+good|do\s+it|sounds?\s+good)\b/i;
const EXPORT_RE = /\b(email|export|send\s+(?:me\s+)?(?:the\s+)?(?:itinerary|pdf)|pdf)\b/i;

export function inferLoadingHint(message: string): LoadingHint {
  const text = message.trim();
  if (!text) {
    return "default";
  }
  if (EXPORT_RE.test(text)) {
    return "export";
  }
  if (CONFIRM_RE.test(text)) {
    return "confirm";
  }
  if (RECOMMEND_RE.test(text)) {
    return "recommend";
  }
  if (EDIT_RE.test(text)) {
    return "edit";
  }
  if (
    EXPLAIN_RE.test(text) ||
    ADVISORY_RE.test(text) ||
    (text.endsWith("?") && /\b(this|it|plan|itinerary|trip)\b/i.test(text))
  ) {
    return "explain";
  }
  if (PLAN_RE.test(text)) {
    return "plan";
  }
  if (text.endsWith("?")) {
    return "clarify";
  }
  return "default";
}

export function isLongRunningHint(hint: LoadingHint): boolean {
  return (
    hint === "plan" ||
    hint === "edit" ||
    hint === "recommend" ||
    hint === "explain" ||
    hint === "export"
  );
}

export function loadingHintMessage(hint: LoadingHint): string {
  switch (hint) {
    case "recommend":
      return "Finding recommendations…";
    case "edit":
      return "Updating your itinerary…";
    case "explain":
      return "Looking that up…";
    case "plan":
      return "Planning your trip…";
    case "confirm":
      return "Generating your itinerary…";
    case "clarify":
      return "Understanding your request…";
    case "export":
      return "Preparing your export…";
    default:
      return "Working on your reply…";
  }
}

export function pendingBubbleMessage(hint: LoadingHint): string {
  switch (hint) {
    case "recommend":
      return "Searching places and travel guides";
    case "edit":
      return "Applying your change and re-checking quality";
    case "explain":
      return "Checking travel guidance for your trip";
    case "plan":
      return "Building your itinerary";
    case "confirm":
      return "Running Planning and quality checks";
    case "clarify":
      return "Updating your trip details";
    case "export":
      return "Sending your itinerary";
    default:
      return "Assistant is thinking";
  }
}

/** Extra line shown after a few seconds so long plan/edit/recommend turns feel alive. */
export function longRunningDetail(hint: LoadingHint, elapsedSec: number): string | null {
  if (elapsedSec < 4 || !isLongRunningHint(hint)) {
    return null;
  }
  if (elapsedSec < 10) {
    switch (hint) {
      case "plan":
        return "Searching places and scheduling your days…";
      case "edit":
        return "Rebuilding the affected day…";
      case "recommend":
        return "Matching places to your interests…";
      case "explain":
        return "Pulling guidance and your itinerary context…";
      case "export":
        return "Talking to the export service…";
      default:
        return null;
    }
  }
  if (elapsedSec < 20) {
    switch (hint) {
      case "plan":
      case "edit":
        return "Review Agent is checking feasibility and grounding…";
      case "recommend":
        return "Almost there…";
      case "explain":
        return "Composing an answer…";
      case "export":
        return "Almost done…";
      default:
        return null;
    }
  }
  switch (hint) {
    case "plan":
    case "edit":
      return "Still working — complex trips can take up to half a minute.";
    case "recommend":
    case "explain":
    case "export":
      return "Still working — thanks for waiting.";
    default:
      return "Still working…";
  }
}

export function activeLoadingMessage(hint: LoadingHint, elapsedSec: number): string {
  const base = loadingHintMessage(hint);
  const detail = longRunningDetail(hint, elapsedSec);
  return detail ? `${base} ${detail}` : base;
}

export function activePendingBubbleMessage(hint: LoadingHint, elapsedSec: number): string {
  const base = pendingBubbleMessage(hint);
  const detail = longRunningDetail(hint, elapsedSec);
  return detail ? `${base} — ${detail}` : base;
}
