from app.chat.infrastructure.adapters import ModelAwareAnswerGeneratorAdapter, TemplateAnswerGeneratorAdapter
from app.chat.infrastructure.llm_adapter import ResolvedModel


def test_model_aware_answer_generator_prefixes_model_tag():
    inner = TemplateAnswerGeneratorAdapter()
    gen = ModelAwareAnswerGeneratorAdapter(
        inner=inner,
        model=ResolvedModel(provider="openai", model_name="gpt-4o"),
    )
    out = gen.generate(question="q", context="ctx", has_hits=True)
    assert out.startswith("[model: openai/gpt-4o]")
