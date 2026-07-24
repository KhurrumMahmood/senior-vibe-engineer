#ifndef CSEMANTIC_SEMANTIC_H
#define CSEMANTIC_SEMANTIC_H

typedef enum job_state {
    JOB_STATE_DONE = 0,
    JOB_STATE_QUEUED = 1,
    JOB_STATE_RUNNING = 2
} job_state;

typedef struct job {
    job_state state;
} job;

typedef struct request_options {
    const char *region;
    int retries;
} request_options;

typedef struct summary {
    int subtotal;
    int tax;
} summary;

typedef enum legacy_status {
    LEGACY_STATUS_PENDING = 0
} legacy_status;

typedef enum canonical_status {
    CANONICAL_STATUS_PENDING = 0
} canonical_status;

void job_queue(job *value);
void job_start(job *value);
void job_finish(job *value);
const char *job_state_wire(job_state value);
request_options options_straggler(void);
request_options options_alpha(void);
request_options options_beta(void);
request_options options_gamma(void);
summary summarize_invoice(int cents);
summary build_statement(int cents);
int invoice_preview(int cents);
int statement_preview(int cents);
int invoke_registered(int value);
canonical_status migrate_status(legacy_status value);
const char *legacy_wire_name(void);

#endif
