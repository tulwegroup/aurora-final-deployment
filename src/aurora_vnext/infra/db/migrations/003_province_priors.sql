-- =============================================================================
-- Aurora OSI vNext — Province Prior Dataset Schema
-- Phase G §G.1 (Province Priors)
--
-- Tectono-stratigraphic province prior database (§8.2).
-- Stores spatial prior probability distributions Π^(c)(r_i) per:
--   - commodity
--   - tectono-stratigraphic province polygon
--   - library version
--
-- Impossible province vetoes (§8.3) are stored as explicit records
-- with prior_probability = 0.0, allowing audit trail.
--
-- Bayesian posterior updates (§8.4) are stored as separate records
-- linked to parent priors — never overwriting baseline priors.
-- =============================================================================

BEGIN;

-- =============================================================================
-- TECTONO-STRATIGRAPHIC PROVINCES — Spatial polygons
-- =============================================================================

CREATE TABLE IF NOT EXISTS tectono_stratigraphic_provinces (
    province_id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    province_code       TEXT        NOT NULL UNIQUE,  -- e.g. "YILGARN_CRATON", "ANDEAN_ARC"
    province_name       TEXT        NOT NULL,
    geological_age      TEXT,       -- e.g. "Archean", "Proterozoic", "Mesozoic"
    tectonic_setting    TEXT,       -- e.g. "Craton", "Orogenic Belt", "Volcanic Arc"
    province_geom       GEOMETRY(MULTIPOLYGON, 4326),  -- PostGIS geometry

    -- Metadata
    data_source         TEXT,
    data_version        TEXT        NOT NULL DEFAULT '0.1.0',
    is_offshore         BOOLEAN     NOT NULL DEFAULT FALSE,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_provinces_code  ON tectono_stratigraphic_provinces(province_code);
CREATE INDEX IF NOT EXISTS idx_provinces_geom  ON tectono_stratigraphic_provinces USING GIST(province_geom);
CREATE INDEX IF NOT EXISTS idx_provinces_offshore ON tectono_stratigraphic_provinces(is_offshore);


-- =============================================================================
-- PROVINCE PRIOR PROBABILITIES — Π^(c)(r_i) per commodity per province
-- =============================================================================

CREATE TABLE IF NOT EXISTS province_prior_probabilities (
    prior_id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    province_id         UUID        NOT NULL REFERENCES tectono_stratigraphic_provinces(province_id),
    commodity_id        UUID        NOT NULL REFERENCES commodity_definitions(commodity_id),
    commodity_name      TEXT        NOT NULL,
    province_code       TEXT        NOT NULL,

    -- Prior probability value Π^(c)(r_i) ∈ [0, 1]
    prior_probability   NUMERIC(8,6) NOT NULL CHECK (prior_probability BETWEEN 0 AND 1),

    -- 95% confidence interval bounds
    ci_95_lower         NUMERIC(8,6) CHECK (ci_95_lower BETWEEN 0 AND 1),
    ci_95_upper         NUMERIC(8,6) CHECK (ci_95_upper BETWEEN 0 AND 1),

    -- Whether this constitutes an impossible-province veto (prior = 0.0 + explicit veto flag)
    is_impossible_province BOOLEAN  NOT NULL DEFAULT FALSE,
    impossibility_reason TEXT,      -- e.g. "No magmatic source within 500km", "Wrong age"

    -- Prior type: baseline (from literature) vs posterior (from ground truth)
    prior_type          TEXT        NOT NULL DEFAULT 'baseline'
                                    CHECK (prior_type IN ('baseline', 'posterior')),

    -- If posterior: link to parent baseline prior and ground truth dataset
    parent_prior_id     UUID        REFERENCES province_prior_probabilities(prior_id),
    ground_truth_dataset_id TEXT,

    -- Library version
    library_version     TEXT        NOT NULL DEFAULT '0.1.0',

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT province_priors_unique
        UNIQUE (province_id, commodity_id, prior_type, library_version),

    CONSTRAINT impossible_province_has_zero_probability
        CHECK (NOT is_impossible_province OR prior_probability = 0.0),

    CONSTRAINT posterior_has_parent
        CHECK (prior_type != 'posterior' OR parent_prior_id IS NOT NULL),

    CONSTRAINT ci_bounds_valid
        CHECK (ci_95_lower IS NULL OR ci_95_upper IS NULL OR ci_95_lower <= ci_95_upper)
);

CREATE INDEX IF NOT EXISTS idx_ppp_province  ON province_prior_probabilities(province_id);
CREATE INDEX IF NOT EXISTS idx_ppp_commodity ON province_prior_probabilities(commodity_id);
CREATE INDEX IF NOT EXISTS idx_ppp_version   ON province_prior_probabilities(library_version);
CREATE INDEX IF NOT EXISTS idx_ppp_impossible ON province_prior_probabilities(commodity_id)
    WHERE is_impossible_province = TRUE;


-- =============================================================================
-- PROVINCE LOOKUP CACHE — Pre-computed cell-to-province mappings
-- Avoids repeated spatial intersection queries during pipeline execution.
-- Cache is invalidated when province geometry or prior versions change.
-- =============================================================================

CREATE TABLE IF NOT EXISTS province_cell_cache (
    cache_id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    lat_center          NUMERIC(10,6) NOT NULL,
    lon_center          NUMERIC(11,6) NOT NULL,
    cell_resolution     NUMERIC(10,6) NOT NULL,  -- Resolution for which this lookup is valid
    province_id         UUID        REFERENCES tectono_stratigraphic_provinces(province_id),
    province_code       TEXT,
    is_offshore         BOOLEAN     NOT NULL DEFAULT FALSE,
    cache_version       TEXT        NOT NULL DEFAULT '0.1.0',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (lat_center, lon_center, cell_resolution, cache_version)
);

CREATE INDEX IF NOT EXISTS idx_pcc_location ON province_cell_cache(lat_center, lon_center);
CREATE INDEX IF NOT EXISTS idx_pcc_province ON province_cell_cache(province_id);


COMMIT;