-- The India Meteorological Department's district-wise 5-day warnings (its API, endpoint
-- districtwarning), stored as ONE replaceable snapshot pushed by scripts/push_imd_warnings.py.
-- The IMD key works only from one registered IP, so the live server cannot fetch this itself;
-- the snapshot carries IMD's own issue time and the dashboard shows both that and how old it is.
-- Every district IMD lists for a north-east state is stored (including "no warning" days) so the
-- dashboard can tell "IMD lists this state and warns nowhere" apart from "IMD's feed does not
-- list this state" (it has no Mizoram districts).
-- codes: IMD's warning codes, comma separated (1 no warning, 2 heavy rain, 16 very heavy rain,
-- 17 extremely heavy rain, 4 thunderstorm/lightning, ...); color: 1 red, 2 orange, 3 yellow, 4 green.
CREATE TABLE IF NOT EXISTS imd_warnings (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state      TEXT NOT NULL CHECK (state IN ('Sikkim','Assam','Arunachal Pradesh','Manipur','Meghalaya','Mizoram','Nagaland','Tripura')),
    district   TEXT NOT NULL,
    obj_id     TEXT NOT NULL,                 -- IMD's district id (the same in every IMD endpoint)
    day        SMALLINT NOT NULL CHECK (day BETWEEN 1 AND 5),
    valid_date DATE NOT NULL,
    codes      TEXT NOT NULL,
    color      SMALLINT NOT NULL CHECK (color BETWEEN 1 AND 4),
    issued_at  TIMESTAMPTZ NOT NULL,          -- when IMD issued it
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (obj_id, day)
);
CREATE INDEX IF NOT EXISTS imd_warnings_state ON imd_warnings (state);
