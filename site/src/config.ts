// Public links. Replace before deploying if these change.
// REPO_REF: the branch holding the evidence. Switch to "main" once merged.
export const REPO = "https://github.com/mtk1606/audit";
export const REPO_REF = "claude/vibrant-pasteur-ppo9f4";

export const LINKS = {
  repository: REPO,
  linkedin: "https://www.linkedin.com/in/mtk1606",
  portfolio: "https://mohamedelkhoudimi.com",
} as const;

export const reportUrl = (path: string): string => `${REPO}/blob/${REPO_REF}/${path}`;
