export function getScoreColorClass(score) {
  if (score === undefined || score === null || !Number.isFinite(Number(score))) {
    return "score-empty";
  }
  if (score >= 80) return "score-strong";
  if (score >= 60) return "score-good";
  if (score >= 40) return "score-neutral";
  return "score-weak";
}
