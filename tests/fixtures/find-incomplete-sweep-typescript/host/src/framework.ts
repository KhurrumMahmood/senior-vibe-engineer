declare const router: {
  get(path: string, options: { cache?: boolean }): void;
};

router.get("/one", { cache: true });
router.get("/two", { cache: true });
router.get("/three", { cache: true });
router.get("/four", {});

export const frameworkShape = true;
