"""A check of New York's matches against the text of the filings, run once by hand on September 26, 2026, and each answer it got, from which the card states the results.

The Department's search API finds a term in a filing's metadata when asked with search_document_text=false, and in its metadata or the text the Department's document library holds for its PDF when asked with true, so a term found only with true is in the text and not in the metadata. The check asked the API about one filing at a time, by its filename (fn:(filename)); the PDFs themselves were not fetched, since their hosts' robots.txt disallow all robots. Five filings chosen by hand (CALIBRATION) were asked first, to see that the restriction, the phrase and OR syntax and the two modes behave as described; they are left out of both draws. GENERIC was at first asked with text alone, so that a title holding its words would have passed for text; after every other answer, it was asked again of each filing without text, and none had it in the metadata, not even the one whose title begins "TO ENACT". Last, the matched name was asked after each other title with which no government is named, such as CITY OF BELLPORT for the Village of Bellport (UNNAMED), to see whether such a phrase turns up where no government can be meant; it can, likely from the filing form, which prints the four titles before "of" and the government's name. checks/ny_precision.py draws the same filings from the published tables.
"""

from collections import Counter

CHECKED = "2026-09-26"
# The draws, fixed before any filing was drawn: SIZES[part] filings by random.Random(SEEDS[part]).sample from the pool sorted by filename; decoys by random.Random(SEEDS["decoy"]).choice, in the order the filings were drawn.
SEEDS = {"main": 20260926, "supplement": 20260927, "decoy": 20260928}
SIZES = {"main": 40, "supplement": 10}
# main: the filings matched by name or name_county, less CALIBRATION; supplement: those matched by name_county, less CALIBRATION and the main draw.
POOLS = {"main": 145_784, "supplement": 1_395}
CALIBRATION = ("090213438010d564.pdf", "0902134380010659.pdf", "090213438000898a.pdf", "090213438031e521.pdf", "09021343800cd1b7.pdf")
GENERIC = '"hereby" OR "enacted"'
OUTCOMES = {
    "confirmed": "the text has the matched government's Census name and the metadata does not",
    "in_metadata": "the metadata has the name too, so the search cannot tell whether the text does",
    "contradicted": "the name is not found and that of a same-name government of another Census type is",
    "not_named": "the text has GENERIC, so the search reads it, and neither name is found",
    "no_text": "neither name is found, nor GENERIC in the text and not the metadata, so the search is not shown to read the text",
}

# Per filing: part, filename, date filed, census_id and Census name of the match, then the API's answers, 1 found and 0 not:
# GENERIC and the Census name, each with text, then metadata only, asked only when the first found it; "COUNTY OF X" OR "X COUNTY" for the government's county, the same way, or None for a county;
# the decoy, another government of the same Census type, and whether its name was found with text; each same-name government of another Census type, counties aside, with its county and whether its name was found with text.
RESULTS = [
    ('main', '090213438000cf6b.pdf', '2009-05-04', '212076', 'VILLAGE OF AMITYVILLE', (1, 0), (1, 0), (0, None), ('VILLAGE OF RIVERSIDE', 0), ()),
    ('main', '090213438000b3d2.pdf', '2011-02-18', '131422', 'TOWN OF CORINTH', (1, 0), (1, 0), (1, 0), ('TOWN OF OVID', 0), (('VILLAGE OF CORINTH', 'SARATOGA', 0),)),
    ('main', '09021343800093fe.pdf', '2011-03-24', '109582', 'CITY OF KINGSTON', (1, 0), (1, 0), (0, None), ('CITY OF ROME', 0), (('TOWN OF KINGSTON', 'ULSTER', 0),)),
    ('main', '090213438004d9c1.pdf', '2002-02-11', '109622', 'TOWN OF MOOERS', (1, 0), (1, 0), (0, None), ('TOWN OF CLARKSTOWN', 0), ()),
    ('main', '0902134380341872.pdf', '2024-02-26', '170490', 'VILLAGE OF EAST AURORA', (1, 0), (1, 0), (0, None), ('VILLAGE OF VERNON', 0), ()),
    ('main', '090213438003322b.pdf', '2003-08-06', '194805', 'CITY OF NEW YORK', (1, 0), (1, 0), (1, 0), ('CITY OF JOHNSTOWN', 0), ()),
    ('main', '090213438000a93f.pdf', '2012-03-16', '131345', 'TOWN OF AMHERST', (1, 0), (1, 0), (1, 0), ('TOWN OF JASPER', 0), ()),
    ('main', '090213438000fb4e.pdf', '2007-03-02', '170793', 'TOWN OF BEEKMAN', (1, 0), (1, 0), (1, 0), ('TOWN OF CATON', 0), ()),
    ('main', '090213438013d94d.pdf', '2016-11-14', '194805', 'CITY OF NEW YORK', (1, 0), (1, 1), (0, None), ('CITY OF NIAGARA FALLS', 0), ()),
    ('main', '090213438032e481.pdf', '2023-09-05', '109639', 'TOWN OF WESTPORT', (1, 0), (1, 0), (1, 0), ('TOWN OF THROOP', 0), ()),
    ('main', '09021343800685a0.pdf', '1998-09-21', '170467', 'VILLAGE OF FREDONIA', (1, 0), (1, 0), (0, None), ('VILLAGE OF MARATHON', 0), ()),
    ('main', '090213438004d615.pdf', '2002-01-17', '109677', 'TOWN OF CORNWALL', (1, 0), (1, 0), (0, None), ('TOWN OF ADAMS', 0), ()),
    ('main', '0902134380010927.pdf', '2006-03-02', '170591', 'VILLAGE OF GOSHEN', (1, 0), (1, 0), (1, 0), ('VILLAGE OF SCOTIA', 0), (('TOWN OF GOSHEN', 'ORANGE', 0),)),
    ('main', '090213438022d196.pdf', '2018-11-23', '170594', 'CITY OF NEWBURGH', (1, 0), (1, 0), (1, 0), ('VILLAGE OF HUNTER', 0), (('TOWN OF NEWBURGH', 'ORANGE', 0),)),
    ('main', '090213438000ba42.pdf', '2011-09-13', '131395', 'TOWN OF VAN BUREN', (1, 0), (1, 0), (1, 0), ('TOWN OF HORICON', 0), ()),
    ('main', '09021343800acd0c.pdf', '2001-01-03', '170415', 'COUNTY OF ALLEGANY', (1, 0), (1, 0), None, ('COUNTY OF SCHENECTADY', 0), (('VILLAGE OF ALLEGANY', 'CATTARAUGUS', 0), ('TOWN OF ALLEGANY', 'CATTARAUGUS', 0))),
    ('main', '09021343803c3c0d.pdf', '2026-02-26', '170895', 'TOWN OF HEMPSTEAD', (1, 0), (0, None), (0, None), ('TOWN OF SALISBURY', 0), (('VILLAGE OF HEMPSTEAD', 'NASSAU', 0),)),
    ('main', '09021343800396ac.pdf', '2003-11-07', '205001', 'TOWN OF SCHAGHTICOKE', (1, 0), (1, 0), (0, None), ('TOWN OF DEPOSIT', 0), (('VILLAGE OF SCHAGHTICOKE', 'RENSSELAER', 0),)),
    ('main', '09021343802fbc0c.pdf', '2021-07-09', '184105', 'TOWN OF FLOYD', (1, 0), (1, 1), (0, None), ('TOWN OF KINGSBURY', 0), ()),
    ('main', '090213438001cf79.pdf', '2006-05-30', '131311', 'TOWN OF VESTAL', (1, 0), (1, 0), (1, 0), ('TOWN OF BEDFORD', 0), ()),
    ('main', '0902134380038e6a.pdf', '2003-09-24', '139356', 'VILLAGE OF KINDERHOOK', (1, 0), (1, 0), (0, None), ('VILLAGE OF RICHFIELD SPRINGS', 0), (('TOWN OF KINDERHOOK', 'COLUMBIA', 0),)),
    ('main', '0902134380010526.pdf', '2007-12-10', '170970', 'TOWN OF STONY POINT', (1, 0), (1, 0), (1, 0), ('TOWN OF PLATTEKILL', 0), ()),
    ('main', '0902134380367519.pdf', '2025-02-11', '109567', 'CITY OF MECHANICVILLE', (1, 0), (1, 0), (0, None), ('VILLAGE OF MATINECOCK', 0), ()),
    ('main', '09021343800adae2.pdf', '2000-10-04', '170644', 'VILLAGE OF BELLPORT', (1, 0), (1, 0), (0, None), ('VILLAGE OF ROSLYN ESTATES', 0), ()),
    ('main', '09021343800e090b.pdf', '2015-04-30', '194802', 'VILLAGE OF ARCADE', (1, 0), (1, 1), (0, None), ('VILLAGE OF EARLVILLE', 0), (('TOWN OF ARCADE', 'WYOMING', 0),)),
    ('main', '0902134380068a40.pdf', '1999-10-08', '170547', 'VILLAGE OF HEWLETT NECK', (1, 0), (1, 0), (1, 0), ('VILLAGE OF WHITEHALL', 0), ()),
    ('main', '0902134380064f1e.pdf', '2008-12-22', '186662', 'VILLAGE OF LIBERTY', (1, 0), (1, 0), (1, 0), ('VILLAGE OF SINCLAIRVILLE', 0), (('TOWN OF LIBERTY', 'SULLIVAN', 0),)),
    ('main', '09021343800beb3a.pdf', '2014-10-23', '202197', 'VILLAGE OF PITTSFORD', (1, 0), (0, None), (0, None), ('VILLAGE OF PLANDOME', 0), (('TOWN OF PITTSFORD', 'MONROE', 0),)),
    ('main', '0902134380009197.pdf', '2012-07-11', '212887', 'VILLAGE OF OSSINING', (1, 0), (1, 0), (0, None), ('VILLAGE OF LANSING', 0), (('TOWN OF OSSINING', 'WESTCHESTER', 0),)),
    ('main', '090213438028ad1e.pdf', '2019-09-20', '170895', 'TOWN OF HEMPSTEAD', (1, 0), (1, 0), (0, None), ('TOWN OF CLAVERACK', 0), (('VILLAGE OF HEMPSTEAD', 'NASSAU', 0),)),
    ('main', '0902134380109323.pdf', '2015-07-27', '139363', 'TOWN OF FRIENDSHIP', (1, 0), (1, 0), (1, 1), ('TOWN OF AVOCA', 0), ()),
    ('main', '09021343803f0de4.pdf', '2026-08-17', '170764', 'TOWN OF CLINTON', (1, 0), (1, 0), (1, 1), ('TOWN OF PORTAGE', 0), (('VILLAGE OF CLINTON', 'ONEIDA', 0),)),
    ('main', '09021343800689f4.pdf', '1998-05-07', '170651', 'VILLAGE OF OCEAN BEACH', (1, 0), (1, 0), (1, 0), ('VILLAGE OF MANLIUS', 0), ()),
    ('main', '0902134380009cce.pdf', '2013-12-20', '171084', 'TOWN OF JERUSALEM', (1, 0), (1, 0), (1, 0), ('TOWN OF EAST OTTO', 0), ()),
    ('main', '090213438000e07f.pdf', '2008-09-04', '170811', 'TOWN OF WALES', (1, 0), (1, 0), (0, None), ('TOWN OF WARREN', 0), ()),
    ('main', '0902134380032bba.pdf', '2004-06-03', '109725', 'TOWN OF MAMARONECK', (1, 0), (1, 0), (1, 0), ('TOWN OF LINDLEY', 0), (('VILLAGE OF MAMARONECK', 'WESTCHESTER', 0),)),
    ('main', '090213438015f176.pdf', '2017-02-27', '208831', 'VILLAGE OF EAST HILLS', (1, 0), (1, 0), (0, None), ('VILLAGE OF NORTH COLLINS', 0), ()),
    ('main', '0902134380320de2.pdf', '2023-02-13', '170551', 'VILLAGE OF LAUREL HOLLOW', (1, 0), (1, 0), (1, 0), ('CITY OF AUBURN', 0), ()),
    ('main', '09021343800327dc.pdf', '2004-11-26', '170806', 'TOWN OF HAMBURG', (1, 0), (1, 0), (0, None), ('TOWN OF UNADILLA', 0), (('VILLAGE OF HAMBURG', 'ERIE', 0),)),
    ('main', '0902134380243a1c.pdf', '2019-02-13', '131438', 'TOWN OF RIVERHEAD', (1, 0), (1, 0), (0, None), ('TOWN OF MOREAU', 0), ()),
    ('supplement', '090213438015819a.pdf', '2017-02-03', '208803', 'COUNTY OF CORTLAND', (1, 0), (1, 0), None, ('COUNTY OF LEWIS', 0), (('CITY OF CORTLAND', 'CORTLAND', 1),)),
    ('supplement', '090213438031ee55.pdf', '2023-01-19', '170714', 'TOWN OF DICKINSON', (1, 0), (1, 0), (1, 1), ('TOWN OF FREMONT', 0), ()),
    ('supplement', '090213438021e188.pdf', '2018-10-03', '131267', 'VILLAGE OF ALBION', (1, 0), (1, 0), (1, 1), ('VILLAGE OF WELLSVILLE', 0), (('TOWN OF ALBION', 'ORLEANS', 1), ('TOWN OF ALBION', 'OSWEGO', 1))),
    ('supplement', '090213438003304e.pdf', '2004-12-23', '109651', 'TOWN OF STARK', (1, 0), (1, 0), (1, 0), ('TOWN OF MORRISTOWN', 0), ()),
    ('supplement', '090213438000fc80.pdf', '2008-01-07', '208927', 'TOWN OF CHESTER', (1, 0), (1, 0), (1, 0), ('TOWN OF ESSEX', 0), (('VILLAGE OF CHESTER', 'ORANGE', 1),)),
    ('supplement', '090213438000fec3.pdf', '2007-05-25', '131397', 'TOWN OF GREENVILLE', (1, 0), (1, 0), (1, 0), ('TOWN OF DUNKIRK', 0), ()),
    ('supplement', '0902134380321bbf.pdf', '2023-02-27', '208815', 'CITY OF CORTLAND', (1, 0), (1, 0), (1, 1), ('VILLAGE OF FARMINGDALE', 0), ()),
    ('supplement', '09021343802ecaa9.pdf', '2021-04-05', '131239', 'CITY OF ROCHESTER', (1, 0), (1, 0), (1, 1), ('VILLAGE OF BABYLON', 0), (('TOWN OF ROCHESTER', 'ULSTER', 0),)),
    ('supplement', '09021343802a1b1a.pdf', '2019-11-29', '131440', 'TOWN OF FREMONT', (1, 0), (1, 0), (1, 1), ('TOWN OF WESTERLO', 0), ()),
    ('supplement', '090213438001d15f.pdf', '2007-01-08', '170942', 'TOWN OF YATES', (1, 0), (1, 0), (1, 0), ('TOWN OF LAPEER', 0), ()),
]

# Asked last, on the same day: for each filing, the matched name after each other Census title with which no New York government in governments is named, asked with text, 1 found and 0 not.
UNNAMED = {
    '090213438000cf6b.pdf': (('COUNTY OF AMITYVILLE', 0), ('CITY OF AMITYVILLE', 0), ('TOWN OF AMITYVILLE', 0)),
    '090213438000b3d2.pdf': (('COUNTY OF CORINTH', 0), ('CITY OF CORINTH', 0)),
    '09021343800093fe.pdf': (('COUNTY OF KINGSTON', 0), ('VILLAGE OF KINGSTON', 0)),
    '090213438004d9c1.pdf': (('COUNTY OF MOOERS', 0), ('CITY OF MOOERS', 0), ('VILLAGE OF MOOERS', 0)),
    '0902134380341872.pdf': (('COUNTY OF EAST AURORA', 0), ('CITY OF EAST AURORA', 0), ('TOWN OF EAST AURORA', 0)),
    '090213438003322b.pdf': (('COUNTY OF NEW YORK', 1), ('TOWN OF NEW YORK', 0), ('VILLAGE OF NEW YORK', 0)),
    '090213438000a93f.pdf': (('COUNTY OF AMHERST', 0), ('CITY OF AMHERST', 0), ('VILLAGE OF AMHERST', 0)),
    '090213438000fb4e.pdf': (('COUNTY OF BEEKMAN', 0), ('CITY OF BEEKMAN', 0), ('VILLAGE OF BEEKMAN', 0)),
    '090213438013d94d.pdf': (('COUNTY OF NEW YORK', 1), ('TOWN OF NEW YORK', 0), ('VILLAGE OF NEW YORK', 0)),
    '090213438032e481.pdf': (('COUNTY OF WESTPORT', 0), ('CITY OF WESTPORT', 0), ('VILLAGE OF WESTPORT', 0)),
    '09021343800685a0.pdf': (('COUNTY OF FREDONIA', 0), ('CITY OF FREDONIA', 0), ('TOWN OF FREDONIA', 0)),
    '090213438004d615.pdf': (('COUNTY OF CORNWALL', 0), ('CITY OF CORNWALL', 0), ('VILLAGE OF CORNWALL', 0)),
    '0902134380010927.pdf': (('COUNTY OF GOSHEN', 0), ('CITY OF GOSHEN', 0)),
    '090213438022d196.pdf': (('COUNTY OF NEWBURGH', 0), ('VILLAGE OF NEWBURGH', 0)),
    '090213438000ba42.pdf': (('COUNTY OF VAN BUREN', 0), ('CITY OF VAN BUREN', 0), ('VILLAGE OF VAN BUREN', 0)),
    '09021343800acd0c.pdf': (('CITY OF ALLEGANY', 0),),
    '09021343803c3c0d.pdf': (('COUNTY OF HEMPSTEAD', 0), ('CITY OF HEMPSTEAD', 0)),
    '09021343800396ac.pdf': (('COUNTY OF SCHAGHTICOKE', 1), ('CITY OF SCHAGHTICOKE', 0)),
    '09021343802fbc0c.pdf': (('COUNTY OF FLOYD', 0), ('CITY OF FLOYD', 0), ('VILLAGE OF FLOYD', 0)),
    '090213438001cf79.pdf': (('COUNTY OF VESTAL', 0), ('CITY OF VESTAL', 0), ('VILLAGE OF VESTAL', 0)),
    '0902134380038e6a.pdf': (('COUNTY OF KINDERHOOK', 0), ('CITY OF KINDERHOOK', 0)),
    '0902134380010526.pdf': (('COUNTY OF STONY POINT', 0), ('CITY OF STONY POINT', 0), ('VILLAGE OF STONY POINT', 0)),
    '0902134380367519.pdf': (('COUNTY OF MECHANICVILLE', 0), ('TOWN OF MECHANICVILLE', 0), ('VILLAGE OF MECHANICVILLE', 0)),
    '09021343800adae2.pdf': (('COUNTY OF BELLPORT', 0), ('CITY OF BELLPORT', 1), ('TOWN OF BELLPORT', 0)),
    '09021343800e090b.pdf': (('COUNTY OF ARCADE', 0), ('CITY OF ARCADE', 0)),
    '0902134380068a40.pdf': (('COUNTY OF HEWLETT NECK', 1), ('CITY OF HEWLETT NECK', 0), ('TOWN OF HEWLETT NECK', 0)),
    '0902134380064f1e.pdf': (('COUNTY OF LIBERTY', 0), ('CITY OF LIBERTY', 0)),
    '09021343800beb3a.pdf': (('COUNTY OF PITTSFORD', 0), ('CITY OF PITTSFORD', 0)),
    '0902134380009197.pdf': (('COUNTY OF OSSINING', 0), ('CITY OF OSSINING', 0)),
    '090213438028ad1e.pdf': (('COUNTY OF HEMPSTEAD', 1), ('CITY OF HEMPSTEAD', 0)),
    '0902134380109323.pdf': (('COUNTY OF FRIENDSHIP', 0), ('CITY OF FRIENDSHIP', 0), ('VILLAGE OF FRIENDSHIP', 0)),
    '09021343803f0de4.pdf': (('CITY OF CLINTON', 0),),
    '09021343800689f4.pdf': (('COUNTY OF OCEAN BEACH', 0), ('CITY OF OCEAN BEACH', 0), ('TOWN OF OCEAN BEACH', 0)),
    '0902134380009cce.pdf': (('COUNTY OF JERUSALEM', 0), ('CITY OF JERUSALEM', 0), ('VILLAGE OF JERUSALEM', 0)),
    '090213438000e07f.pdf': (('COUNTY OF WALES', 0), ('CITY OF WALES', 0), ('VILLAGE OF WALES', 0)),
    '0902134380032bba.pdf': (('COUNTY OF MAMARONECK', 0), ('CITY OF MAMARONECK', 0)),
    '090213438015f176.pdf': (('COUNTY OF EAST HILLS', 0), ('CITY OF EAST HILLS', 0), ('TOWN OF EAST HILLS', 0)),
    '0902134380320de2.pdf': (('COUNTY OF LAUREL HOLLOW', 0), ('CITY OF LAUREL HOLLOW', 0), ('TOWN OF LAUREL HOLLOW', 0)),
    '09021343800327dc.pdf': (('COUNTY OF HAMBURG', 0), ('CITY OF HAMBURG', 0)),
    '0902134380243a1c.pdf': (('COUNTY OF RIVERHEAD', 0), ('CITY OF RIVERHEAD', 0), ('VILLAGE OF RIVERHEAD', 0)),
    '090213438015819a.pdf': (('TOWN OF CORTLAND', 0), ('VILLAGE OF CORTLAND', 1)),
    '090213438031ee55.pdf': (('COUNTY OF DICKINSON', 0), ('CITY OF DICKINSON', 0), ('VILLAGE OF DICKINSON', 0)),
    '090213438021e188.pdf': (('COUNTY OF ALBION', 0), ('CITY OF ALBION', 0)),
    '090213438003304e.pdf': (('COUNTY OF STARK', 0), ('CITY OF STARK', 0), ('VILLAGE OF STARK', 0)),
    '090213438000fc80.pdf': (('COUNTY OF CHESTER', 0), ('CITY OF CHESTER', 0)),
    '090213438000fec3.pdf': (('COUNTY OF GREENVILLE', 0), ('CITY OF GREENVILLE', 0), ('VILLAGE OF GREENVILLE', 0)),
    '0902134380321bbf.pdf': (('TOWN OF CORTLAND', 0), ('VILLAGE OF CORTLAND', 1)),
    '09021343802ecaa9.pdf': (('COUNTY OF ROCHESTER', 0), ('VILLAGE OF ROCHESTER', 0)),
    '09021343802a1b1a.pdf': (('COUNTY OF FREMONT', 0), ('CITY OF FREMONT', 0), ('VILLAGE OF FREMONT', 0)),
    '090213438001d15f.pdf': (('CITY OF YATES', 0), ('VILLAGE OF YATES', 1)),
}
# New York County, one of the five counties within New York City, has no row in governments, since the Census does not count those counties as governments; so COUNTY OF NEW YORK names a real county, was asked only through that oversight, and is left out of the counts.
REAL = ("COUNTY OF NEW YORK",)


def in_text(answers):
    """Whether a term asked with text, then without it, was found only with it: in the text and not the metadata."""
    text, metadata = answers
    return bool(text and not metadata)


def outcome(generic, name, other):
    if in_text(name):
        return "confirmed"
    if name[0]:
        return "in_metadata"
    if any(found for _, _, found in other):
        return "contradicted"
    return "not_named" if in_text(generic) else "no_text"


def unnamed(filename):
    """The UNNAMED phrases asked of a filing that name no government, with their answers."""
    return tuple((phrase, found) for phrase, found in UNNAMED.get(filename, ()) if phrase not in REAL)


def summary():
    """Per part: filings, outcomes, filings with GENERIC, the name or the county's name in the text and not the metadata, decoys found, filings with a same-name government of another type and those found to name one, filings asked UNNAMED phrases that name no government and those in which one was found, and the earliest and latest filing dates."""
    parts = {}
    for part, filename, filed, census_id, census_name, generic, name, county, decoy, other in RESULTS:
        entry = parts.setdefault(part, {"filings": 0, "outcomes": Counter(), "with_text": 0, "decoys_found": 0, "with_other": 0, "other_found": 0, "unnamed_asked": 0, "unnamed_found": 0, "first_filed": filed, "last_filed": filed})
        entry["filings"] += 1
        entry["outcomes"][outcome(generic, name, other)] += 1
        entry["with_text"] += in_text(generic) or in_text(name) or (county is not None and in_text(county))
        entry["decoys_found"] += decoy[1]
        entry["with_other"] += bool(other)
        entry["other_found"] += any(found for _, _, found in other)
        entry["unnamed_asked"] += bool(unnamed(filename))
        entry["unnamed_found"] += any(found for _, found in unnamed(filename))
        entry["first_filed"], entry["last_filed"] = min(entry["first_filed"], filed), max(entry["last_filed"], filed)
    return parts
