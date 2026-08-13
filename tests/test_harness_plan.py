from src.client.harness_plan import ClientHarnessPlanPolicy
from src.cli import CLI


def test_client_harness_plan_tracks_advice_dag_and_round_trips():
    policy = ClientHarnessPlanPolicy()
    plan = policy.build("分析A股", {"intent": "market", "needs_mcp": True})
    assert plan.steps[3].depends_on == ("evidence", "cognition")
    for step in plan.steps:
        policy.mark(plan, step.step_id, "completed")
    restored = policy.from_dict(policy.to_dict(plan))
    assert restored.status == "completed"
    assert restored.steps[1].evidence_required is True


def test_client_harness_plan_is_preserved_in_non_persistent_agent_plan():
    policy = ClientHarnessPlanPolicy()
    harness_plan = policy.to_dict(policy.build("评估私募入池", {"intent": "private_fund"}))
    cli = CLI()

    cli._remember_agent_plan(
        query="评估私募入池",
        intent_plan={
            "intent": "private_fund",
            "needs_mcp": False,
            "_harness_plan": harness_plan,
        },
        mapping_query="评估私募入池",
        mcp_data={},
        matches=[],
        synthesis={},
        provider="openai",
        model="gpt-test",
        persist=False,
    )

    assert cli._last_agent_plan["harness_plan"] == harness_plan
    assert cli._last_agent_plan["harness_plan"]["steps"][0]["step_id"] == "intent"
