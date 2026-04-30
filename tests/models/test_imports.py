def test_model_deps_importable():
    import huggingface_hub  # noqa: F401
    import llama_cpp  # noqa: F401
    import sentence_transformers  # noqa: F401
    import torch  # noqa: F401
    import transformers  # noqa: F401
