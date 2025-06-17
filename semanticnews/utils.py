import json
import numpy as np
from openai import OpenAI
from functools import wraps
from django.views.decorators.cache import cache_page
from django.utils.translation import get_language


def anonymous_only_cache(timeout):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            lang = getattr(request, 'LANGUAGE_CODE', get_language())
            return cache_page(timeout, key_prefix=lang)(view_func)(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


def is_json(text):
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return False
    else:
        return True


def translate(to_translate_dict, from_to='tr_to_en', model='gpt-4o-mini'):
    content = ''
    for key in to_translate_dict.keys():
        content += f'{key}: {to_translate_dict[key]}\n'

    messages = [{
        'role': 'system',
        'content': f"Translate the parts of the article from "
                   f"{'Turkish to English' if from_to == 'tr_to_en' else 'English to Turkish'}. "
                   f"Respond in JSON format with keys: {', '.join(to_translate_dict.keys())}"
    }, {
        'role': 'user',
        'content': content,
    }]

    # Use a fresh OpenAI client and close its HTTP transport promptly
    with OpenAI() as client:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            response_format={'type': 'json_object'}
        )
    result = json.loads(response.choices[0].message.content)

    return result


def get_relevance(embedding1, embedding2):
    """
    Calculate the cosine similarity between the topic's embedding and the video chunk's embedding.
    This similarity score serves as a measure of relevance between them.
    """
    # Convert the embeddings to numpy arrays
    v1 = np.array(embedding1, dtype=float)
    v2 = np.array(embedding2, dtype=float)

    if v1.shape != v2.shape:
        return

    # Calculate the norms (magnitudes) of the vectors
    norm_1 = np.linalg.norm(v1)
    norm_2 = np.linalg.norm(v2)

    # Compute the cosine similarity (dot product divided by the product of norms)
    relevance = np.dot(v1, v2) / (norm_1 * norm_2)

    return float(relevance)
