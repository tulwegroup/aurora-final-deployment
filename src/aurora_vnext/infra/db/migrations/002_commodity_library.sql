-- =============================================================================
-- Aurora OSI vNext — Commodity Spectral Library Schema
-- Phase G §G.1 (Commodity Abstraction)
--
-- Designed to support 40+ commodities from day one.
-- Each commodity carries:
--   1. unique observable weighting vectors (Θ_c evidence weights)
--   2. spectral response curves per mineral-system family
--   3. depth kernel parameters per commodity
--   4. environmental regime modifiers (onshore / offshore / combined)
--   5. negative evidence definitions (confounders)
--
-- NO spectral coefficients or scoring logic are stored here at Phase G.
-- The schema captures the structure; values are populated in Phase F/A.
-- =============================================================================

BEGIN;

-- =============================================================================
-- MINERAL SYSTEM FAMILIES — 9 canonical families from Phase A
-- =============================================================================

CREATE TABLE IF NOT EXISTS mineral_system_families (
    family_id           TEXT        PRIMARY KEY,  -- 'A'..'I'
    family_name         TEXT        NOT NULL,
    description         TEXT,
    dag_template        JSONB,      -- Causal DAG node template for this family
    default_theta_c     JSONB,      -- Default Θ_c parameter block (populated Phase F)
    hard_veto_conditions JSONB,     -- Veto conditions common to all commodities in family
    library_version     TEXT        NOT NULL DEFAULT '0.1.0',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO mineral_system_families (family_id, family_name, description) VALUES
    ('A', 'Orogenic / Structurally Controlled Hydrothermal', 'Gold-dominated structurally hosted systems'),
    ('B', 'Porphyry / Epithermal / Intrusive',               'Copper-gold porphyry and epithermal systems'),
    ('C', 'IOCG / Iron-Rich Metasomatic',                    'Iron-oxide copper-gold metasomatic systems'),
    ('D', 'Magmatic Mafic-Ultramafic',                       'Nickel-PGE-chromite in mafic/ultramafic hosts'),
    ('E', 'Sedimentary / Basin-Hosted',                      'Uranium-vanadium-coal in sedimentary basins'),
    ('F', 'Pegmatite / Granite / Rare-Metal',                'Lithium-tantalum-cesium in pegmatite bodies'),
    ('G', 'Carbonatite / Alkaline / REE',                    'Rare earth element carbonatite-alkaline systems'),
    ('H', 'Diamonds / Kimberlite / Lamproite',               'Diamond indicator mineral kimberlite systems'),
    ('I', 'Seabed / Offshore Systems',                        'Polymetallic nodules, SMS, phosphorite offshore')
ON CONFLICT (family_id) DO NOTHING;


-- =============================================================================
-- COMMODITY DEFINITIONS — 40 target commodities
-- One row per commodity. Version-tracked for lineage.
-- =============================================================================

CREATE TABLE IF NOT EXISTS commodity_definitions (
    commodity_id        UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                TEXT        NOT NULL UNIQUE,  -- e.g. "gold", "copper", "lithium"
    symbol              TEXT,       -- e.g. "Au", "Cu", "Li"
    family_id           TEXT        NOT NULL REFERENCES mineral_system_families(family_id),

    -- Deposit model list for this commodity (from Phase A)
    deposit_models      TEXT[],     -- e.g. ['orogenic_gold', 'epithermal_low_sulphidation']

    -- Dominant observable modalities (ordered by importance for evidence scoring)
    dominant_modalities TEXT[],     -- e.g. ['spectral', 'structural', 'magnetic']

    -- Whether this commodity has offshore applicability
    offshore_applicable BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Whether this commodity has depth kernel defined
    depth_kernel_defined BOOLEAN    NOT NULL DEFAULT FALSE,

    -- Library version this definition belongs to
    library_version     TEXT        NOT NULL DEFAULT '0.1.0',

    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Pre-populate 40 commodity stubs (names only — full Θ_c params added in Phase F)
INSERT INTO commodity_definitions (name, symbol, family_id, dominant_modalities, offshore_applicable) VALUES
    ('gold',            'Au',   'A', ARRAY['spectral','structural','magnetic','gravity'], FALSE),
    ('silver',          'Ag',   'A', ARRAY['spectral','structural','thermal'],            FALSE),
    ('copper',          'Cu',   'B', ARRAY['spectral','magnetic','gravity','structural'], FALSE),
    ('molybdenum',      'Mo',   'B', ARRAY['spectral','gravity','thermal'],               FALSE),
    ('porphyry_gold',   'Au',   'B', ARRAY['spectral','structural','gravity'],            FALSE),
    ('iocg_copper',     'Cu',   'C', ARRAY['magnetic','gravity','spectral','sar'],        FALSE),
    ('magnetite',       'Fe',   'C', ARRAY['magnetic','gravity'],                         FALSE),
    ('nickel',          'Ni',   'D', ARRAY['magnetic','gravity','spectral'],              FALSE),
    ('platinum',        'Pt',   'D', ARRAY['magnetic','gravity','thermal'],               FALSE),
    ('palladium',       'Pd',   'D', ARRAY['magnetic','gravity'],                         FALSE),
    ('chromite',        'Cr',   'D', ARRAY['magnetic','gravity','spectral'],              FALSE),
    ('cobalt',          'Co',   'D', ARRAY['magnetic','spectral','gravity'],              FALSE),
    ('uranium',         'U',    'E', ARRAY['spectral','sar','gravity'],                   FALSE),
    ('vanadium',        'V',    'E', ARRAY['spectral','gravity'],                         FALSE),
    ('coal',            'C',    'E', ARRAY['spectral','sar','thermal'],                   FALSE),
    ('phosphate',       'P',    'E', ARRAY['spectral','gravity','sar'],                   TRUE),
    ('lithium',         'Li',   'F', ARRAY['spectral','magnetic','gravity'],              FALSE),
    ('tantalum',        'Ta',   'F', ARRAY['spectral','gravity','magnetic'],              FALSE),
    ('niobium',         'Nb',   'F', ARRAY['spectral','gravity','magnetic'],              FALSE),
    ('cesium',          'Cs',   'F', ARRAY['spectral','gravity'],                         FALSE),
    ('tin',             'Sn',   'F', ARRAY['spectral','gravity','magnetic'],              FALSE),
    ('tungsten',        'W',    'F', ARRAY['spectral','gravity','magnetic'],              FALSE),
    ('rare_earth',      'REE',  'G', ARRAY['spectral','magnetic','gravity'],              FALSE),
    ('niobium_ree',     'Nb',   'G', ARRAY['spectral','gravity','magnetic'],              FALSE),
    ('diamond',         'C',    'H', ARRAY['spectral','gravity','structural'],            FALSE),
    ('kimberlite_ind',  'KIM',  'H', ARRAY['spectral','gravity','magnetic'],              FALSE),
    ('manganese_nodule','Mn',   'I', ARRAY['spectral','gravity','hydro'],                 TRUE),
    ('seafloor_massive','SMS',  'I', ARRAY['spectral','thermal','gravity','hydro'],       TRUE),
    ('cobalt_rich_crust','Co',  'I', ARRAY['spectral','gravity','hydro'],                 TRUE),
    ('offshore_phosphorite','P','I', ARRAY['spectral','gravity','sar','hydro'],           TRUE),
    ('zinc',            'Zn',   'B', ARRAY['spectral','structural','gravity'],            FALSE),
    ('lead',            'Pb',   'B', ARRAY['spectral','structural','gravity'],            FALSE),
    ('iron_ore',        'Fe',   'C', ARRAY['magnetic','gravity','spectral'],              FALSE),
    ('titanium',        'Ti',   'D', ARRAY['spectral','magnetic','gravity'],              FALSE),
    ('zircon',          'Zr',   'D', ARRAY['spectral','gravity'],                         FALSE),
    ('graphite',        'C',    'E', ARRAY['spectral','sar'],                             FALSE),
    ('potash',          'K',    'E', ARRAY['spectral','gravity','sar'],                   FALSE),
    ('bauxite',         'Al',   'A', ARRAY['spectral','thermal','sar'],                   FALSE),
    ('antimony',        'Sb',   'A', ARRAY['spectral','structural'],                      FALSE),
    ('bismuth',         'Bi',   'B', ARRAY['spectral','thermal','structural'],            FALSE)
ON CONFLICT (name) DO NOTHING;


-- =============================================================================
-- OBSERVABLE WEIGHTING VECTORS — Per-commodity evidence weights w^(c)_k
-- One row per commodity per library_version.
-- Weights define how each of the 42 observables contributes to evidence score.
-- =============================================================================

CREATE TABLE IF NOT EXISTS observable_weighting_vectors (
    weight_id           UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    commodity_id        UUID        NOT NULL REFERENCES commodity_definitions(commodity_id),
    commodity_name      TEXT        NOT NULL,
    library_version     TEXT        NOT NULL DEFAULT '0.1.0',

    -- Weight vector: 42 fields mapping observable_key → weight value
    -- { "x_spec_1": 0.15, "x_sar_1": 0.08, "x_grav_1": 0.12, ... }
    -- Weights are normalised (sum = 1.0 per commodity)
    -- NULL values indicate the observable is not used for this commodity
    weights             JSONB       NOT NULL DEFAULT '{}',

    -- Weight category metadata: which modality groups dominate
    dominant_weight_fraction NUMERIC(5,4),  -- Fraction held by dominant modality group

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (commodity_id, library_version)
);


-- =============================================================================
-- SPECTRAL RESPONSE CURVES — Mineral-specific reflectance signatures
-- Defines the spectral response expected for each commodity-family pair.
-- Used by services/harmonization.py for cross-mission normalisation.
-- =============================================================================

CREATE TABLE IF NOT EXISTS spectral_response_curves (
    curve_id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    commodity_id        UUID        NOT NULL REFERENCES commodity_definitions(commodity_id),
    family_id           TEXT        NOT NULL REFERENCES mineral_system_families(family_id),
    curve_name          TEXT        NOT NULL,
    library_version     TEXT        NOT NULL DEFAULT '0.1.0',

    -- Wavelength-reflectance pairs: [ {"wl_nm": 450, "reflectance": 0.12}, ... ]
    wavelength_reflectance JSONB    NOT NULL DEFAULT '[]',

    -- Spectral band mappings for each supported satellite mission
    -- { "Sentinel-2": {"B4": 0.12, "B8": 0.45, ...}, "Landsat-9": {...} }
    mission_band_mappings JSONB     NOT NULL DEFAULT '{}',

    -- Diagnostic absorption features for this mineral
    -- [ {"wavelength_nm": 2200, "feature": "Al-OH", "depth": 0.08}, ... ]
    absorption_features JSONB       DEFAULT '[]',

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (commodity_id, curve_name, library_version)
);


-- =============================================================================
-- DEPTH KERNEL PARAMETERS — Per-commodity D^(c)(z, z_expected) (§15.2)
-- Controls how ACIF values project to 3D voxel depths in the digital twin.
-- =============================================================================

CREATE TABLE IF NOT EXISTS depth_kernel_params (
    kernel_id           UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    commodity_id        UUID        NOT NULL REFERENCES commodity_definitions(commodity_id),
    family_id           TEXT        NOT NULL REFERENCES mineral_system_families(family_id),
    library_version     TEXT        NOT NULL DEFAULT '0.1.0',

    -- Expected depth range for this commodity-family pair
    depth_expected_m    NUMERIC(10,2) NOT NULL CHECK (depth_expected_m >= 0),
    depth_min_m         NUMERIC(10,2) NOT NULL CHECK (depth_min_m >= 0),
    depth_max_m         NUMERIC(10,2) NOT NULL CHECK (depth_max_m > depth_min_m),
    depth_uncertainty_m NUMERIC(10,2) CHECK (depth_uncertainty_m >= 0),

    -- Kernel shape parameters (Gaussian / exponential / empirical)
    kernel_type         TEXT        NOT NULL DEFAULT 'gaussian'
                                    CHECK (kernel_type IN ('gaussian','exponential','empirical')),
    kernel_params       JSONB       NOT NULL DEFAULT '{}',
                                    -- gaussian: {"sigma": 150.0}
                                    -- exponential: {"lambda": 0.005}
                                    -- empirical: {"depth_points": [...], "weights": [...]}

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (commodity_id, library_version)
);


-- =============================================================================
-- ENVIRONMENTAL REGIME MODIFIERS — Adjusts Θ_c for environment type
-- Allows same commodity to have different parameter sets for
-- onshore, offshore, and combined environments.
-- =============================================================================

CREATE TABLE IF NOT EXISTS environmental_regime_modifiers (
    modifier_id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    commodity_id        UUID        NOT NULL REFERENCES commodity_definitions(commodity_id),
    environment         TEXT        NOT NULL CHECK (environment IN ('ONSHORE','OFFSHORE','COMBINED')),
    library_version     TEXT        NOT NULL DEFAULT '0.1.0',

    -- Multiplicative modifiers on the base weight vector
    -- { "x_off_1": 1.5, "x_grav_1": 0.8, ... }
    weight_modifiers    JSONB       NOT NULL DEFAULT '{}',

    -- Additional causal gate conditions active only for this environment
    additional_gates    JSONB       DEFAULT '[]',

    -- Offshore-specific: minimum required water depth for applicability
    min_water_depth_m   NUMERIC(10,2),
    max_water_depth_m   NUMERIC(10,2),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (commodity_id, environment, library_version)
);


COMMIT;