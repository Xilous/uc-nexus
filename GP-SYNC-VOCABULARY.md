gp sync vocabulary

agreed names for how UC Nexus and Dynamics GP exchange data through the relay. use these terms in conversation, docs, PR text and issue text. code identifiers keep their existing names; each entry ends with the code it maps to.

traffic types

- mirrored GP data - GP records Nexus keeps a copy of on a schedule: jobs and purchase orders. GP is the authority. the copy is overwritten, never compared. code: gp_job_sync, gp_po_sync
- live GP lookups - GP data fetched at the moment a form opens or an action runs, never stored: vendors, buyers, cost codes, customers, customer addresses, employees, tax codes, PO totals, vendor email. code: the gp_* queries in app/schemas/relay.py
- nexus to gp writes - requests for GP to create or change a record when a person saves something in Nexus: PO registration, GP receive entry, create job, create buyer, add customer address, change job site. code: relay ops create_po, create_receipt, create_job, create_buyer, create_customer_address, update_job_site
- nexus relay gp handshake - what the relay tells Nexus about itself when it connects: the GP company list with names, its build, and the requests it supports. code: the hello frame, relay_gateway.note_hello

mirrored GP data

- GP jobs sync - every 15 minutes per company, GP's job list is read and a project is created for every job Nexus lacks. existing projects are left untouched. code: gp_job_sync
- gp job health check - the per-job check that its cost codes point at accounts the company owns, stamped on the project by GP jobs sync and re-run live at PO registration. code: job_setup_health, check_job_setup_live
- first time gp company nexus initialization - the one-time copy of a company's entire PO history, 25 at a time, resumable after any stop, allowed only in the overnight initialization window. until it finishes, that company gets no open-POs sync. code: backfill (_run_backfill, backfill_cursor, backfill_done)
- open-POs sync - the repeating pass, at least 15 minutes apart per company, that re-copies every PO still open in GP. code: incremental / open-book walk (_run_incremental, open_only)
- open-POs reconciliation - the second half of an open-POs sync: POs Nexus still holds open that GP did not list as open are read by number to learn their final state. code: closure sweep (_sweep_closed, read_pos_by_number, po_numbers_left_open)
- GP-deleted PO rule - a PO GP has no record of, open or finished, is cancelled in Nexus only after two consecutive open-POs syncs miss it. it is cancelled the same way as a GP void; nothing in the UI says it was deleted. code: note_missing_from_gp, gp_missing_since
- PO status from quantities - a mirrored PO's status comes from received and cancelled quantities plus which GP table it sits in, never from GP's status code. nothing received: GP_REGISTERED. some: PARTIALLY_RECEIVED. all, or in GP's finished table: CLOSED. everything cancelled: CANCELLED. never written below PARTIALLY_RECEIVED, so VENDOR_CONFIRMED survives. code: derive_po_stage
- GP-owned fields / Nexus-only fields - the PO fields every open-POs sync overwrites from GP (vendor, order date, line quantities, unit cost, received amount) versus the fields it never touches (notes, vendor quote number, cost code, creator, shipping, tariff, request number, the VENDOR_CONFIRMED step, and the project on a Nexus-registered PO). code: NEXUS_ONLY_FIELDS
- mirror progress - the saved per-company record of how far the initialization got, whether it finished, and where the current open-POs sync is up to. survives restarts and redeploys. code: gp_po_sync_state

protection of GP

- GP read limit - everything scheduled may ask GP for at most 100 POs or jobs per minute in total, across all companies, and never more than 25 in one request. code: gp_load budget, READS_PER_MINUTE, READ_BATCH
- GP CPU pause - scheduled reads stop when GP's SQL CPU is at or above 40 percent and continue only when below 40. the relay applies the same line on its side and refuses scheduled requests. code: SERVER_CPU_PAUSE_PCT, SERVER_CPU_RESUME_PCT, relay load_ceiling_pct
- overnight initialization window - 8pm to 5am Toronto time, the only hours a first time gp company nexus initialization may run. nothing else is gated by it. code: GP_PO_SYNC_BACKFILL_WINDOW, gp_window

nexus to gp writes

- PO registration - a PO drafted in Nexus is sent to GP, GP assigns the number and books the job cost, Nexus stores the number. the register shows it as GP-Registered. code: register_po_in_gp, relay create_po
- GP receive entry - the warehouse receives against a PO and Nexus writes the receipt into GP, where it waits in a batch for someone to post inside GP. code: relay create_receipt
- pending GP writes - nexus to gp writes held while the relay is unreachable and sent automatically when it returns. a write that may already have reached GP is never retried blindly. code: gp_outbox
