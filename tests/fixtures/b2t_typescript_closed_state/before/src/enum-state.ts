export enum ImportedJobState {
  QUEUED = "queued",
  RUNNING = "running",
}

export interface ImportedJob {
  state: ImportedJobState;
}

export const importedIsQueued = (job: ImportedJob): boolean =>
  job.state === ImportedJobState.QUEUED;
