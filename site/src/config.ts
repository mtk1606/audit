// Public links. REPO_REF is the branch the evidence links point to.
// After merging to main it must be "main" (the default below). While the work
// lives only on a feature branch, set it to that branch name instead.
export const REPO = "https://github.com/mtk1606/audit";
export const REPO_REF = "main";

export const LINKS = {
  repository: REPO,
  linkedin: "https://www.linkedin.com/in/mtk1606",
  portfolio: "https://mohamedelkhoudimi.com",
} as const;

// Folders use GitHub's tree view, files its blob view.
export const reportUrl = (path: string): string =>
  `${REPO}/${/\.[a-z0-9]+$/i.test(path) ? "blob" : "tree"}/${REPO_REF}/${path}`;
