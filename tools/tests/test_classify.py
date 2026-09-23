import unittest

from lib import classify as c


class TestClassify(unittest.TestCase):
    def test_kind(self):
        self.assertEqual(c.kind('Blade HQ dealer Exclusive. Black hardware', 'Limited'), 'Blade HQ excl.')
        self.assertEqual(c.kind('Moteng Distributor Exclusive', 'Limited'), 'Moteng excl.')
        self.assertEqual(c.kind('Sprintrun', '1200'), 'Sprint Run')
        self.assertEqual(c.kind("Part of Spyderco's Salt series of knives", ''), 'Regular production')
        self.assertEqual(c.kind('Limited. Originally slated as a sprintrun, it proved so', ''), 'Limited')
        self.assertEqual(c.kind('', 'Regular production'), 'Regular production')

    def test_norm(self):
        self.assertEqual(c.norm_dealer("St. Nick's excl."), "St. Nick's Knives excl.")
        self.assertEqual(c.norm_dealer('H.L. Dalis Inc. excl.'), 'H.L. Dalis excl.')
        self.assertEqual(c.norm_dealer('Manix 2 lightweight. Black polymer cage. KnifeCenter excl.'), 'KnifeCenter excl.')

    def test_tag_date(self):
        self.assertEqual(c.tag('Sprint Run'), '🟥 Sprint Run')
        self.assertEqual(c.tag('Limited'), '🟪 Limited')
        self.assertEqual(c.date_key('Jan. 15, 2019 @ 11AM CST'), (2019, 1))
        self.assertEqual(c.date_key('late 90s?'), (9999, 0))
        self.assertEqual(c.start_year('2014-2026'), '2014')
        self.assertEqual(c.start_year('late 90s?'), '?')

    def test_first_date(self):
        self.assertEqual(c.first_date('Jan. 2019 / Feb. 2020'), 'Jan. 2019')
        self.assertEqual(c.first_date('Jan. 2019, Feb. 2020'), 'Jan. 2019')

    def test_clean_qty(self):
        self.assertEqual(c.clean_qty('Limited'), '')
        self.assertEqual(c.clean_qty('Sprint run'), '')
        self.assertEqual(c.clean_qty('Regular production'), '')
        self.assertEqual(c.clean_qty('N/A'), '')
        self.assertEqual(c.clean_qty('1200'), '1200')
        self.assertEqual(c.clean_qty('Limited to 1200 pieces worldwide'), 'Limited to 1200 pieces worldwide')


FAM = {
    "sections": ["Para-Military", "ParaMilitary 2", "ParaMilitary 2 Lightweight"],
    "section_rules": [
        {"section": "ParaMilitary 2 Lightweight", "field": "handle", "regex": "FRN|FRCP"},
        {"section": "Para-Military", "field": "wiki_table", "regex": "^Variations of the Paramilitary$"},
        {"section": "ParaMilitary 2", "field": "sku", "regex": "2$"},
    ],
}


def _rec(**kw):
    base = {"table": "Variations of the Paramilitary 2", "sku": "C81GP2", "handle": "Black G-10", "edge": "PE",
            "steel": "CPM-S30V", "from_to": "2010-", "note": "", "number_made": "Regular production"}
    base.update(kw)
    return base


class TestClassifyRecord(unittest.TestCase):
    def test_full_row(self):
        rec = _rec(sku="C81GPBK2 (Forum)", from_to="Jan. 2019 / Feb. 2020",
                   note="Blade HQ dealer Exclusive", number_made="1200")
        self.assertEqual(c.classify_record(FAM, rec), {
            "sku": "C81GPBK2", "section": "ParaMilitary 2", "released": "Jan. 2019", "steel": "CPM-S30V",
            "handle": "Black G-10", "type": "Blade HQ excl.", "qty": "1200"})

    def test_rules_first_match_wins(self):
        rec = _rec(table="Variations of the Paramilitary", handle="Black FRN")
        self.assertEqual(c.classify_record(FAM, rec)["section"], "ParaMilitary 2 Lightweight")
        rec = _rec(table="Variations of the Paramilitary", sku="C81GP")
        self.assertEqual(c.classify_record(FAM, rec)["section"], "Para-Military")

    def test_no_match_first_section(self):
        rec = _rec(table="Other", sku="C81GP")
        self.assertEqual(c.classify_record(FAM, rec)["section"], "Para-Military")
        self.assertEqual(c.classify_record({"sections": ["Only"]}, rec)["section"], "Only")

    def test_regular_qty_cleared(self):
        self.assertEqual(c.classify_record(FAM, _rec())["qty"], "")
        self.assertEqual(c.classify_record(FAM, _rec())["type"], "Regular production")


if __name__ == '__main__':
    unittest.main()
