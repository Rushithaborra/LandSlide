-- State scoping for authority contacts and citizen reports, so the dashboard's state
-- selector can show each state's own contacts and reports (and a critical broadcast
-- can ring the right officials instead of everyone in the table).
--
-- authority_contacts.state: NULL means "all states" (a national / NER-wide contact,
-- shown under every state). Contacts that were registered before this column existed
-- were all Sikkim's, so they are set to Sikkim exactly once -- inside the guard, so
-- re-running this file (scripts/migrate.py re-applies every migration) can never turn
-- a later national contact into a Sikkim one.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns WHERE table_name = 'authority_contacts' AND column_name = 'state'
    ) THEN
        ALTER TABLE authority_contacts ADD COLUMN state TEXT;
        UPDATE authority_contacts SET state = 'Sikkim';
    END IF;
END $$;

DO $$
BEGIN
    ALTER TABLE authority_contacts
        ADD CONSTRAINT authority_contacts_state_check CHECK (
            state IS NULL OR state IN ('Sikkim','Assam','Arunachal Pradesh','Manipur','Meghalaya','Mizoram','Nagaland','Tripura')
        );
EXCEPTION WHEN duplicate_object THEN
    NULL;  -- already applied
END $$;

-- citizen_reports.state: worked out when the report is submitted (from its zone, or the
-- nearest assessed zone to its coordinates). NULL = could not be worked out (a report
-- with only a place name and no coordinates); those show under "All States" only.
ALTER TABLE citizen_reports ADD COLUMN IF NOT EXISTS state TEXT;
CREATE INDEX IF NOT EXISTS citizen_reports_state ON citizen_reports (state);
