from evals.run_intent_eval import intent_accuracy


def test_intent_accuracy_scores_matching_prediction():
    score = intent_accuracy(
        outputs={"intent": "credit"},
        reference_outputs={"intent": "credit"},
    )

    assert score is True


def test_intent_accuracy_rejects_wrong_prediction():
    score = intent_accuracy(
        outputs={"intent": "exchange"},
        reference_outputs={"intent": "credit"},
    )

    assert score is False
