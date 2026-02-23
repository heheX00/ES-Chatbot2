import copy

from services.query_safety import QuerySafetyLayer, SafetyStatus, ALWAYS_EXCLUDE_FIELDS


def test_blocks_invalid_top_level_key():
    safety = QuerySafetyLayer(max_result_docs=20, max_agg_buckets=50)
    q = {"query": {"match_all": {}}, "delete": {"foo": "bar"}}
    res = safety.validate(q)
    assert res.status == SafetyStatus.BLOCKED
    assert res.query is None
    assert res.reason.startswith("invalid_top_level_key:")


def test_blocks_script_any_depth_dict():
    safety = QuerySafetyLayer()
    q = {"query": {"bool": {"filter": [{"script": {"source": "1+1"}}]}}}
    res = safety.validate(q)
    assert res.status == SafetyStatus.BLOCKED
    assert res.reason == "script_detected"


def test_blocks_script_any_depth_list():
    safety = QuerySafetyLayer()
    q = {"query": [{"bool": {"must": [{"match_all": {}}, {"nested": {"path": "x", "query": {"script": {"source": "x"}}}}]}}]}
    res = safety.validate(q)
    assert res.status == SafetyStatus.BLOCKED
    assert res.reason == "script_detected"


def test_caps_size_and_marks_modified():
    safety = QuerySafetyLayer(max_result_docs=20)
    q = {"query": {"match_all": {}}, "size": 10000}
    res = safety.validate(q)
    assert res.status == SafetyStatus.MODIFIED
    assert res.query["size"] == 20
    assert "size_capped" in res.reason


def test_injects_source_excludes_when_missing():
    safety = QuerySafetyLayer()
    q = {"query": {"match_all": {}}, "size": 1}
    res = safety.validate(q)
    assert res.status == SafetyStatus.MODIFIED
    assert "_source" in res.query
    assert "excludes" in res.query["_source"]
    for f in ALWAYS_EXCLUDE_FIELDS:
        assert f in res.query["_source"]["excludes"]


def test_merges_source_excludes_without_duplicates():
    safety = QuerySafetyLayer(always_exclude_fields=["a", "b"])
    q = {"query": {"match_all": {}}, "_source": {"excludes": ["b", "c"]}}
    res = safety.validate(q)
    assert res.status == SafetyStatus.MODIFIED
    assert res.query["_source"]["excludes"] == ["b", "c", "a"]


def test_caps_terms_agg_bucket_size():
    safety = QuerySafetyLayer(max_agg_buckets=50)
    q = {
        "size": 0,
        "aggs": {
            "top_people": {
                "terms": {"field": "V2Persons.V1Person.keyword", "size": 1000}
            }
        }
    }
    res = safety.validate(q)
    assert res.status == SafetyStatus.MODIFIED
    assert res.query["aggs"]["top_people"]["terms"]["size"] == 50


def test_caps_nested_terms_aggs():
    safety = QuerySafetyLayer(max_agg_buckets=10)
    q = {
        "size": 0,
        "aggs": {
            "sources": {
                "terms": {"field": "V2SrcCmnName.V2SrcCmnName.keyword", "size": 999},
                "aggs": {
                    "themes": {
                        "terms": {"field": "V2EnhancedThemes.V2Theme.keyword", "size": 999}
                    }
                },
            }
        },
    }
    res = safety.validate(q)
    assert res.status == SafetyStatus.MODIFIED
    assert res.query["aggs"]["sources"]["terms"]["size"] == 10
    assert res.query["aggs"]["sources"]["aggs"]["themes"]["terms"]["size"] == 10


def test_already_safe_query_is_allowed():
    safety = QuerySafetyLayer(max_result_docs=20, max_agg_buckets=50, always_exclude_fields=[])
    q = {"query": {"match_all": {}}, "size": 5, "_source": {"excludes": []}}
    res = safety.validate(q)
    assert res.status == SafetyStatus.ALLOWED
    assert res.reason is None
