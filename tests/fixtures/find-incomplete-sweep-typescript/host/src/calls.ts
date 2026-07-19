import { buildRequest as importedBuildRequest, completeRequest, deliver, stableRequest } from "@app/options.js";

const buildRequestAlias = importedBuildRequest;
const inheritedRegion = { region: "us" as const, stage: "live" as const };

export const first = importedBuildRequest({ id: "first", region: "us", stage: "live" }); // swept
export const second = buildRequestAlias({ id: "second", ...inheritedRegion }); // swept
export const third = importedBuildRequest({ id: "third", ...inheritedRegion }); // swept

export const forgotten = importedBuildRequest({ id: "forgotten", stage: "live" });

export const stableFirst = stableRequest({ id: "stable-first", region: "global" });
export const stableSecond = stableRequest({ id: "stable-second", region: "global" });
export const stableThird = stableRequest({ id: "stable-third", region: "global" });
export const stableDefault = stableRequest({ id: "stable-default" });

export const completeFirst = completeRequest({ id: "complete-first", region: "us" });
export const completeSecond = completeRequest({ id: "complete-second", region: "us" });
export const completeThird = completeRequest({ id: "complete-third", region: "us" });
export const completeFourth = completeRequest({ id: "complete-fourth", region: "us" });

export const audited = deliver({ id: "audited", audit: true });
export const deferred = deliver({ id: "deferred" });

void first;
void second;
void third;
void forgotten;
void stableFirst;
void stableSecond;
void stableThird;
void stableDefault;
void completeFirst;
void completeSecond;
void completeThird;
void completeFourth;
void audited;
void deferred;
