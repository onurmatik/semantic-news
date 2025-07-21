# Product Requirements Document (PRD)

## Project Title: semantic.news

### Overview

**semantic.news** is an open-source platform for building collective memory around significant events. It allows users to create "topics" that relate and contextualize news content across time, supported by AI-generated suggestions and community contributions. The platform is designed for researchers, journalists, and engaged citizens who want to follow and understand the development of complex issues over time.

---

## Goals

- Enable users to **create and manage topics** that collect and relate news content.
- Suggest relevant content using AI-powered fetching from predefined sources (RSS, YouTube, etc.).
- Allow **content annotation**, visualization, and collaborative editing.
- Facilitate **community-driven curation** and contextualization of current events.
- Build a platform that can be deployed globally, adapted locally, and extended by contributors.

---

## Stack

- **Backend**: Django
- **Task Queue**: Celery
- **Database**: AWS RDS (PostgreSQL)
- **Infrastructure**: AWS EC2
- **Frontend**: Bootstrap (HTML/CSS/JS)

---

## Core Concepts

### 1. Topics

Topics represent a curated collection of related events or content. They can vary in scope:

- Broad: `Judicial Politicization in Turkey`
- Mid-level: `Appointment of Trustees to Opposition Municipalities`
- Specific: `Legal Actions Against Ekrem İmamoğlu`

#### Requirements

- Users create and own topics.
- Topics are **unique per user** (URL structure: `/username/topic-slug/`).
- Topics can be **edited** by the creator and **collaboratively updated** by others.
- Topic metadata includes:
  - Title
  - Description
  - Tags
  - Visibility (Public / Private)

### 2. Content

Content is any external URL representing a piece of news, video, blog post, etc.

#### Requirements

- Periodic fetching from predefined sources:
  - RSS feeds
  - YouTube channel transcripts
- User can manually add content via URL input.
- Platform performs **relevance checks** between content and topic (based on semantic embeddings).
- Irrelevant content may be rejected based on a configurable threshold.
- Each content entry stores:
  - URL
  - Title
  - Date
  - Source
  - Embedding vector (for semantic similarity)
  - Optional user notes

### 3. Annotations

Annotations are **modular summaries and visualizations** generated for a topic by processing its content.

#### Examples

- Topic recap (text summary)
- Event timeline
- Entity graph (people, organizations, locations)
- Sentiment progression
- Media coverage map

#### Requirements

- Modular: annotations can be added or removed by topic owner.
- Dynamically updated when new content is added.
- Open for community suggestions and enhancements.

### 4. Collaboration Model

Inspired by Git workflows, adapted with natural language for non-technical users.

#### Workflow

- A user creates a topic.
- Another user can **fork** the topic and modify its content relationships.
- The forked version can be submitted as a **merge suggestion** (PR equivalent).
- The original topic owner can:
  - Accept or reject the update
  - Merge contributions
  - Add contributor credits
- Forked topics can **sync** with the original topic if updates occur.
- UI uses human-friendly terminology (e.g., “Suggest update” instead of “Pull request”).

### 5. Opinions and Comments

Users can:

- Comment on:
  - Specific content items
  - Annotations
  - Overall topic
- Upvote or react to opinions.
- Topic owners can **accept** external opinions and embed them into the topic.

---

## User Roles

- **Anonymous Visitors**: View public topics and content.
- **Registered Users**:
  - Create topics
  - Add and annotate content
  - Comment and suggest updates to others' topics
- **Topic Owners**:
  - Moderate contributions
  - Accept/merge suggested updates
  - Enable/disable annotations

---

## MVP Scope

- User registration and profile
- Topic creation and per-user uniqueness
- Content ingestion (manual + automated)
- Basic relevance filtering using embeddings
- Annotation engine (with recap + timeline)
- Fork-and-suggest-update flow
- Comments on content and annotations

---
