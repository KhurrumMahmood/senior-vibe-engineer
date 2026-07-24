#ifndef C_PROPOSAL_LEGACY_H
#define C_PROPOSAL_LEGACY_H

int load_credentials(void);
int rotate_credentials(void);
int authorize_admin(void);
int validate_admin(void);
int render_export(void);
int write_export(void);
int save_invoice(void);
int load_invoice(void);

#endif
