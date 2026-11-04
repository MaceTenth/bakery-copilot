"""The eval runner's own plumbing, with the fake model: no network, no cost."""
from app.agent import FakeModelClient
from evals import run as evals_run


def test_case_history_reaches_the_model_as_earlier_turns(client):
    fake = FakeModelClient()
    case = {"id": "t", "input": "Do you have airplane tickets?",
            "history": [{"role": "user", "content": "how much does vanilla cost?"},
                        {"role": "assistant", "content": "We usually pay $89 per litre to Madagascar Vanilla Co."}]}
    result = evals_run.run_case(case, fake)
    sent = fake.last_messages
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[0]["content"] == "how much does vanilla cost?"
    assert "Madagascar Vanilla Co." in sent[1]["content"]
    assert sent[2]["content"][-1]["text"] == "Do you have airplane tickets?"
    assert result["status"] == "ok"


def test_case_without_history_is_a_single_turn(client):
    fake = FakeModelClient()
    evals_run.run_case({"id": "t", "input": "Revenue by branch for August 2026"}, fake)
    assert [m["role"] for m in fake.last_messages] == ["user"]
