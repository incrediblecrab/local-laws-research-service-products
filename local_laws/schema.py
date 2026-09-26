"""The two tables' columns and what each means. The card's schema tables and the verify check both read from here."""

import pyarrow as pa

GOVERNMENTS = pa.schema([
    ("census_id", pa.string()),
    ("census_gid", pa.string()),
    ("name", pa.string()),
    ("government_type", pa.string()),
    ("state", pa.string()),
    ("state_fips", pa.string()),
    ("county_fips", pa.string()),
    ("county_name", pa.string()),
    ("fips_place", pa.string()),
    ("special_district_function", pa.string()),
    ("school_level", pa.string()),
    ("population", pa.int64()),
    ("population_year", pa.int32()),
    ("enrollment", pa.int64()),
    ("enrollment_year", pa.int32()),
    ("web_address", pa.string()),
    ("is_active", pa.bool_()),
])

GOVERNMENT_DOCS = {
    "census_id": "The Census Bureau's 6-digit ID for the government (`CENSUS_ID_PID6`). Unique; the key to join on",
    "census_gid": "The Census Bureau's legacy 14-digit government ID (`CENSUS_ID_GIDID`), which it stopped generating in 2022; null where the source has none",
    "name": "The name as the Census publishes it, in capitals, such as COUNTY OF AUTAUGA or PRATTVILLE HOUSING AUTHORITY",
    "government_type": "`county`, `municipal`, `township`, `special_district` or `school_district`, the Census's five types of local government. `municipal` covers cities, villages, boroughs and incorporated towns; `township` is what the Census calls town or township governments",
    "state": "Postal abbreviation of the state the government is in, looked up from `state_fips`. The source's own `STATE` column belongs to the mailing address",
    "state_fips": "2-digit FIPS state code (`FIPS_STATE`)",
    "county_fips": "3-digit FIPS county code (`FIPS_COUNTY`) of the county area in `county_name`",
    "county_name": "The county area the Census classifies the government as serving (`COUNTY_AREA_NAME`); for a government that crosses county lines, the one it serves most or where it is headquartered",
    "fips_place": "General-purpose governments only (`FIPS_PLACE`). For a municipality, its 5-digit Census place code; for a township, its county subdivision code; for a county, 99 followed by the county code. Null for special and school districts",
    "special_district_function": "Special districts only: the Census function code and name (`FUNCTION_NAME`), such as 24 - LOCAL FIRE PROTECTION",
    "school_level": "Independent school districts only: the grades served (`SCHOOL_LEVEL_DESCRIPTION`), such as 03 - ELEMENTARY AND SECONDARY",
    "population": "General-purpose governments only: the Census Bureau's population estimate for the government (`POPULATION`) for `population_year`",
    "population_year": "The year of `population` (`POPULATION_YEAR`)",
    "enrollment": "Independent school districts only: enrollment (`ENROLLMENT`) in `enrollment_year`",
    "enrollment_year": "The year of `enrollment` (`ENROLLMENT_YEAR`)",
    "web_address": "The website reported to the Census (`WEB_ADDRESS`), which says it did minimal quality control on these addresses; not checked here. Null where none was reported",
    "is_active": "False where the Census marks the government dormant (`IS_ACTIVE` = N): not disincorporated, but not financially active. The Census counts dormant governments, so they are rows",
}

LOCUS_CROSSWALK = pa.schema([
    ("locus_state", pa.string()),
    ("locus_jurisdiction_type", pa.string()),
    ("locus_name", pa.string()),
    ("locus_rows", pa.int64()),
    ("census_id", pa.string()),
    ("match", pa.string()),
    ("candidates", pa.list_(pa.string())),
    ("text_type", pa.string()),
    ("text_type_mentions", pa.int64()),
    ("text_mentions", pa.int64()),
    ("text_fits", pa.bool_()),
])

LOCUS_DOCS = {
    "locus_state": "LOCUS's `state`: a lowercase postal abbreviation",
    "locus_jurisdiction_type": "LOCUS's `source_jurisdiction_type`: `cities` or `counties`",
    "locus_name": "LOCUS's `city` value for cities and `county` value for counties, as LOCUS writes it, such as batavia_city or saint_tammany_parish",
    "locus_rows": "How many rows LOCUS holds for this jurisdiction at the pinned revision",
    "census_id": "The matched government in `governments`; null when `match` is `ambiguous` or `unmatched`",
    "match": "How `census_id` was found, one of the methods under Matching",
    "candidates": "When several same-name governments fit (`municipal_preferred`, `text_type`, `text_county` and `ambiguous`), the `census_id` of each; otherwise empty",
    "text_type": "The type word LOCUS's text most often writes with the government's name, counted over all the jurisdiction's rows: `city` for \"City of Batavia\" or \"Batavia City\". The words looked for are city, town, village, borough, township, plantation, county, parish and municipality. For several candidates, their names are all looked for. Null when the text never writes the name with one of these words, or when no government fits",
    "text_type_mentions": "How many times the text writes `text_type` with the name",
    "text_mentions": "How many times the text writes the name with any of the type words. 0 means the text never names the government this way, which can mean a Census name the text does not use (METROPOLITAN GOVERNMENT OF NASHVILLE-DAVIDSON COUNTY) or text filed under the wrong jurisdiction",
    "text_fits": "Whether `text_type` is a word the matched government's Census title allows (`town` for TOWN OF BARRE; city, county, parish, borough, municipality or town for a consolidated government). Null when `text_mentions` is under 3, when `census_id` is null, or when the Census title has no type word to compare",
}

TABLES = {
    "governments": {"file": "data/governments.parquet", "schema": GOVERNMENTS, "docs": GOVERNMENT_DOCS},
    "locus_crosswalk": {"file": "data/locus_crosswalk.parquet", "schema": LOCUS_CROSSWALK, "docs": LOCUS_DOCS},
}
