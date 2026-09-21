"""SBC leaf pages: per-challenge requirement lines ("how to complete it")."""

from __future__ import annotations

from fc26.ingest.sbc import parse_sbc

_URL = "https://www.fut.gg/sbc/challenges/27-14-manchester-calling/"


def _challenge(name: str, price: str, reqs: str) -> str:
    return (
        f'{{id:1,eaId:18,game:"27",challengeType:"OPEN_CHALLENGE",scoreRequirement:null,'
        f'setEaId:6,name:"{name}",description:"Build it.",imagePath:"x.png",awardsIds:$R[22]=[],'
        f'cheapestSolutionId:1,cheapestSolutionPrice:{price},cheapestSolutionUrl:"/27/sb/a/",'
        f'cheapestSolutionPcId:2,cheapestSolutionPricePc:7300,cheapestSolutionPcUrl:"/27/sb/b/",'
        f"requirementsText:$R[23]=[{reqs}],isStreamlined:!1,awards:$R[24]=[]}}"
    )


_LEAF = (
    '<script>slug:"27-14-manchester-calling",categoryEaId:3,name:"Manchester Calling",'
    'description:"Two squads.",isRepeatable:!1,numberOfRepeats:0,challenges:$R[20]=['
    + _challenge("City", "12000", '"Min. 2 Players from: Manchester City","Min. Team Rating: 82"')
    + ","
    + _challenge("United", "null", '"Min. Team Rating: 84","Min. Chemistry: 20"')
    + "]</script>"
)


def test_each_challenge_lists_its_requirements_and_price():
    record = parse_sbc(_LEAF, _URL)
    assert [c["name"] for c in record["challenges"]] == ["City", "United"]
    assert record["challenges"][0]["requirements"] == [
        "Min. 2 Players from: Manchester City", "Min. Team Rating: 82",
    ]
    assert record["challenges"][0]["cost"] == 12000
    assert record["challenges"][1]["cost"] is None        # unpriced, never invented
    assert record["cost"] == 12000 and record["cost_complete"] is False


def test_page_without_challenge_payload_yields_empty_list():
    record = parse_sbc('<script>slug:"27-1-x",categoryEaId:2,name:"X",description:""</script>', _URL)
    assert record["challenges"] == []
