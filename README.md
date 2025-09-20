# Semantic News

## Setup

1. Copy the example environment file and adjust values as needed:

```bash
cp .env.example .env
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run database migrations and start the development server as usual.

## Installing as a dependency

To include Semantic News in another project, reference the Git repository directly in your `pyproject.toml` or `requirements.txt`:

```bash
pip install "semantic-news @ git+https://github.com/onurmatik/semantic-news.git@main"
```
