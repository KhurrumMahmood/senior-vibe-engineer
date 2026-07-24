#ifndef CBILLING_INVOICE_H
#define CBILLING_INVOICE_H

typedef enum billing_state {
    BILLING_PENDING = 1,
    BILLING_PAID = 2
} billing_state;

typedef struct billing_invoice {
    int quantity;
    int unit_price;
    billing_state state;
} billing_invoice;

int billing_pending_total(int quantity, int unit_price);
int billing_queued_total(int quantity, int unit_price);
int billing_state_code(billing_state state);

#endif
