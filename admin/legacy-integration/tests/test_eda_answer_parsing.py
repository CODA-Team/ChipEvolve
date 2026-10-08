"""Repeated identical answers have one meaning; conflicting answers stay ambiguous."""
import pytest

from qualification.v3.run_model import parse_answer


def test_repeated_identical_json_answers_are_one_semantic_answer():
    first = '{"answer":{"count":4,"bbox":[1,2,3,4]}}'
    reordered = '{"answer":{"bbox":[1,2,3,4],"count":4}}'
    content = '```json\n' + first + '\n```\nExplanation.\n```json\n' + reordered + '\n```'
    assert parse_answer(content) == {'answer': {'count': 4, 'bbox': [1, 2, 3, 4]}}


@pytest.mark.parametrize('other', ['{"answer":{"count":5}}', '{"answer":{"count":true}}'])
def test_distinct_answer_content_is_never_arbitrarily_selected(other):
    with pytest.raises(ValueError, match='one unambiguous JSON answer object'):
        parse_answer('{"answer":{"count":1}}\nExplanation\n' + other)


def test_original_report_array_does_not_hide_a_separately_declared_final_object():
    content = 'Original power report:\n```json\n[{"internal":0.003,"total":0.004}]\n```\n'
    content += '{"answer":{"internal_w":0.003,"total_w":0.004}}'
    assert parse_answer(content) == {'answer': {'internal_w': 0.003, 'total_w': 0.004}}


def test_fenced_object_cannot_hide_a_conflicting_answer_outside_the_fence():
    with pytest.raises(ValueError, match='one unambiguous JSON answer object'):
        parse_answer('```json\n{"answer":{"count":1}}\n```\n{"answer":{"count":2}}')


def test_an_array_is_not_an_answer_object_even_when_its_rows_look_like_answers():
    with pytest.raises(ValueError, match='answer must be a JSON object'):
        parse_answer('[{"answer":{"count":1}}]')
    with pytest.raises(ValueError, match='one unambiguous JSON answer object'):
        parse_answer('Original only:\n```json\n[{"answer":{"count":1}}]\n```')
