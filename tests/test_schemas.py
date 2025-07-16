import pytest
from pydantic import ValidationError
from backend.schemas import ToolModel, StepModel, PlanModel

def test_tool_model_valid():
    tool_data = {"name": "execute_script"}
    tool = ToolModel(**tool_data)
    assert tool.name == "execute_script"

def test_tool_model_invalid():
    with pytest.raises(ValidationError):
        ToolModel(name=123)  # name should be a string

def test_step_model_valid():
    step_data = {
        "tool": {"name": "execute_script"},
        "parameters": {"command": "echo 'hello world'"},
        "reason": "Print hello world"
    }
    step = StepModel(**step_data)
    assert step.tool.name == "execute_script"
    assert step.parameters == {"command": "echo 'hello world'"}
    assert step.reason == "Print hello world"

def test_step_model_invalid_tool():
    with pytest.raises(ValidationError):
        StepModel(
            tool={"name": 123},  # Invalid tool name (should be a string)
            parameters={"command": "echo 'hello world'"},
            reason="Print hello world"
        )

def test_step_model_missing_fields():
    with pytest.raises(ValidationError):
        StepModel(
            tool={"name": "execute_script"},
            parameters={"command": "echo 'hello world'"}
            # Missing 'reason' field
        )

def test_plan_model_valid():
    plan_data = {
        "plan": [
            {
                "tool": {"name": "execute_script"},
                "parameters": {"command": "echo 'hello world'"},
                "reason": "Print hello world"
            },
            {
                "tool": {"name": "execute_script"},
                "parameters": {"command": "ls"},
                "reason": "List directory contents"
            }
        ]
    }
    plan = PlanModel(**plan_data)
    assert len(plan.plan) == 2
    assert plan.plan[0].tool.name == "execute_script"
    assert plan.plan[0].parameters == {"command": "echo 'hello world'"}
    assert plan.plan[0].reason == "Print hello world"
    assert plan.plan[1].tool.name == "execute_script"
    assert plan.plan[1].parameters == {"command": "ls"}
    assert plan.plan[1].reason == "List directory contents"

def test_plan_model_invalid_step():
    with pytest.raises(ValidationError):
        PlanModel(
            plan=[
                {
                    "tool": {"name": "execute_script"},
                    "parameters": {"command": "echo 'hello world'"},
                    "reason": "Print hello world"
                },
                {
                    "tool": {"name": 123},  # Invalid tool name (should be a string)
                    "parameters": {"command": "ls"},
                    "reason": "List directory contents"
                }
            ]
        )

def test_plan_model_missing_fields():
    with pytest.raises(ValidationError):
        PlanModel(
            plan=[
                {
                    "tool": {"name": "execute_script"},
                    "parameters": {"command": "echo 'hello world'"}
                    # Missing 'reason' field
                }
            ]
        )

def test_plan_model_empty_plan():
    with pytest.raises(ValidationError):
        PlanModel(plan=[])  # Empty plan is not allowed

def test_plan_model_invalid_plan_format():
    with pytest.raises(ValidationError):
        PlanModel(plan="invalid_plan_format")  # Plan should be a list of steps
