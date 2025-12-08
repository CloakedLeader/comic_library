from types import SimpleNamespace

from metadata_cleaning import MetadataProcessing


class MockParser:
    def __init__(self, title, series, volume_num=None):
        self.raw_info = SimpleNamespace(
            title=title, series=series, volume_num=volume_num, filepath=""
        )


def test_real_example():
    parser = MockParser(title="Vol. 1: No Good Deed", series="Harley Quinn")
    proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
    result = proc.title_parsing()

    assert result["series"] == "Harley Quinn"
    assert result["title"] == "No Good Deed"
    assert result["volume_num"] == 1


def test_ambig_title():
    parser = MockParser(
        title="Volume 2", series="Fantastic Four by Ryan North: Four Stories About Hope"
    )
    proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
    result = proc.title_parsing()

    assert result["series"] == "Fantastic Four by Ryan North"
    assert result["title"] == "Four Stories About Hope"
    assert result["volume_num"] == 2


def test_basic_colon_in_title():
    parser = MockParser(
        title="Vol. 2: Children of the Atom", series="Ultimate X-Men by Peach Momoko"
    )
    proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
    result = proc.title_parsing()

    assert result["series"] == "Ultimate X-Men by Peach Momoko"
    assert result["title"] == "Children of the Atom"
    assert result["volume_num"] == 2


# ! Change logic in metadata_cleaning so that comics with no numbers are given issue #1.
# def test_hc_in_title():
#     parser = MockParser(title="HC", series="Plastic Man No More!")
#     proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
#     result = proc.title_parsing()

#     assert result["series"] == "Plastic Man No More!"
#     assert result["title"] == "Plastic Man No More!"
#     assert result["volume_num"] == 1


def test_basic_colon_in_series():
    parser = MockParser(title="", series="Daredevil: Born Again")
    proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
    result = proc.title_parsing()

    assert result["series"] == "Daredevil"
    assert result["title"] == "Born Again"


def test_colon_in_title():
    parser = MockParser(title="Batman: The Court of Owls", series="Batman")
    proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
    result = proc.title_parsing()

    assert result["series"] == "Batman"
    assert result["title"] == "The Court of Owls"


def test_ambiguous_title_tpb():
    parser = MockParser(title="TPB", series="Captain America")
    proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
    result = proc.title_parsing()

    assert result["title"] == "Captain America"
    assert result["collection_type"] == 1


def test_series_override_keyword():
    parser = MockParser(title="X-Men Vol. 2", series="X-Men Omnibus")
    proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
    result = proc.title_parsing()

    assert result["collection_type"] == 2

# ! Ignore this test for PR purposes. This is not the topic of this branch.
# def test_volume_number_numeric():
#     parser = MockParser(title="Vol. 4", series="Thor")
#     proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
#     result = proc.title_parsing()

#     assert result["volume_num"] == 4
#     assert result["title"] == ""  # no subtitle present


def test_volume_number_word():
    parser = MockParser(title="Book Three", series="Justice League")
    proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
    result = proc.title_parsing()

    assert result["volume_num"] == 3


def test_volume_with_subtitle():
    parser = MockParser(title="Vol. 3: Born Again", series="Daredevil")
    proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
    result = proc.title_parsing()

    assert result["volume_num"] == 3
    assert result["title"] == "Born Again"


def test_no_volume_falls_back_to_raw():
    parser = MockParser(title="The Killing Joke", series="Batman", volume_num=None)
    proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
    result = proc.title_parsing()

    assert result["title"] == "The Killing Joke"
    assert result["series"] == "Batman"
    assert result["volume_num"] == 0  # fallback behaviour


def test_volume_error_returns_zero():
    parser = MockParser(
        title="Book Thirteen",  # unsupported word-number
        series="Spawn",
    )
    proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
    result = proc.title_parsing()

    assert result["volume_num"] == 0


def test_title_case_applied():
    parser = MockParser(title="vol. 2: the dark phoenix saga", series="uncanny x-men")
    proc = MetadataProcessing(parser.raw_info)  # type: ignore[arg-type]
    result = proc.title_parsing()

    assert result["title"] == "The Dark Phoenix Saga"
    assert result["series"] == "Uncanny X-men"
