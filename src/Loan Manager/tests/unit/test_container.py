"""Container and event bus tests."""
import pytest

from loan_manager.application.event_bus import EventBus


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []

        class MyEvent:
            pass

        bus.subscribe(MyEvent, lambda e: received.append(e))

        event = MyEvent()
        bus.publish(event)
        assert len(received) == 1
        assert received[0] is event

    def test_publish_no_subscribers(self):
        bus = EventBus()

        class MyEvent:
            pass

        # Should not raise
        bus.publish(MyEvent())

    def test_multiple_subscribers(self):
        bus = EventBus()
        received_a = []
        received_b = []

        class MyEvent:
            pass

        bus.subscribe(MyEvent, lambda e: received_a.append(1))
        bus.subscribe(MyEvent, lambda e: received_b.append(2))

        bus.publish(MyEvent())
        assert len(received_a) == 1
        assert len(received_b) == 1


class TestAgentWiring:
    """KCH-239: construct only -- nothing here opens a database or a socket."""

    def test_injected_llm_and_sql_recorder(self):
        from loan_manager.application.agent.tool_registry import ToolRegistry
        from loan_manager.application.use_cases.agent.run_agent_turn import RunAgentTurn
        from loan_manager.container import Container
        from loan_manager.infrastructure.repositories.sqlalchemy_turn_recorder import (
            SqlAlchemyTurnRecorder,
        )

        class FakeLLM:
            def complete(self, messages, tools=None):  # pragma: no cover - never called
                raise AssertionError("construction must not call the model")

        container = Container()
        llm = FakeLLM()

        turn = container.get_run_agent_turn(llm=llm)

        assert isinstance(turn, RunAgentTurn)
        assert isinstance(container.turn_recorder, SqlAlchemyTurnRecorder)
        assert turn._recorder is container.turn_recorder
        assert turn._llm is llm
        registry = turn._propose_registry_for(user_request="lend", turn_id="t-1")
        assert isinstance(registry, ToolRegistry)
        assert registry.mode("create_loan").value == "propose"

    def test_default_llm_is_the_openrouter_client_built_from_settings(self, monkeypatch):
        from loan_manager.container import Container
        from loan_manager.infrastructure.llm import settings as llm_settings
        from loan_manager.infrastructure.llm.openai_compat_client import OpenAICompatClient

        fake_settings = llm_settings.LLMSettings(
            base_url="https://openrouter.ai/api/v1", model="m", api_key_env="KCH239_TEST_KEY",
            temperature=0.1, max_steps=6, timeout_s=60,
        )
        monkeypatch.setattr(llm_settings, "load_llm_settings", lambda: fake_settings)
        monkeypatch.setenv("KCH239_TEST_KEY", "not-a-real-key")

        turn = Container().get_run_agent_turn()

        assert isinstance(turn._llm, OpenAICompatClient)

    def test_start_agent_conversation_is_wired(self):
        from loan_manager.application.use_cases.agent.start_agent_conversation import (
            StartAgentConversation,
        )
        from loan_manager.container import Container

        assert isinstance(Container().get_start_agent_conversation(), StartAgentConversation)
