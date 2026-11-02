"""CR-W08 (B 11/01, lead 11/02): MOPS press releases write amounts with Chinese units
(5,118億5,700萬元). A claim quoting them correctly must not be flagged not_supported, a
wrong number must still be, and conflicts only compare numbers with the same unit."""

from agents.review_checks import chinese_amounts, find_conflicts, paragraph_contains


def test_chinese_amounts_converted_to_yuan():
    assert chinese_amounts("合併營收約為新台幣5,118億5,700萬元") == [511857000000.0]
    assert chinese_amounts("553億9仟9佰萬元，較前月641億8仟3佰萬元") == [55399000000.0, 64183000000.0]
    assert chinese_amounts("約新台幣1兆4,942億4千萬元") == [1494240000000.0]
    assert chinese_amounts("稅後純益約新台幣7,630億6千萬元") == [763060000000.0]
    assert chinese_amounts("營業利益為新台幣271億2佰萬元") == [27102000000.0]


def test_plain_numbers_are_not_read_as_chinese_amounts():
    assert chinese_amounts("EPS 29.43元，增加50.9%") == []
    assert chinese_amounts("營業收入合計 2,525,894,433 千元") == []  # 千元 tables keep the old path


def test_claim_matching_chinese_amount_is_supported():
    para = "聯發科九月營收為新台幣553億9仟9佰萬元"
    assert paragraph_contains(para, 55399000000)  # 元
    assert paragraph_contains(para, 553.99)       # 億元


def test_wrong_number_is_still_not_supported():
    assert not paragraph_contains("聯發科九月營收為新台幣553億9仟9佰萬元", 55300000000)


def test_conflicts_compare_only_the_same_unit():
    evs = [{"evidence_version_id": "a", "paragraph": "九月營收5,118億元"},
           {"evidence_version_id": "b", "paragraph": "營收增加了50.9%"}]
    assert find_conflicts(evs) == []
    evs.append({"evidence_version_id": "c", "paragraph": "九月營收5,200億元"})
    assert find_conflicts(evs) == [{"keyword": "營收", "values": {"a": 5118.0, "c": 5200.0}}]
