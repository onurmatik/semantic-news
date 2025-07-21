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
- Topics are **unique per user** and published under a canonical URL: `/username/topic-slug/`.
- Topics can start in **draft** mode. Once published, they are **public** and cannot be made private.
- Topics can be **edited** by the creator and **collaboratively updated** by others.
- Topic metadata includes:
  - Title
  - Description
  - Tags
  - Status: Draft / Published

### 2. Content

Content is any external URL representing a piece of news, video, blog post, etc.

#### Requirements

- Periodic fetching from predefined sources (RSS feeds, YouTube channels).
- Users can manually add content by submitting URLs.
- All content entries are **globally unique** by URL.
- For the MVP, relevance checks are **not enforced**.
- Each content object includes:
  - URL
  - Title
  - Date
  - Source
  - Embedding vector (for semantic similarity)
  - Optional user notes

### 3. Annotations

Annotations are summaries, visualizations, or derived metadata based on the topic’s content.

#### Examples

- Topic recap (text summary)
- Event timeline
- Entity graph (people, organizations, locations)
- Sentiment progression
- Media coverage map

#### Requirements

- Modular: annotations can be added or removed by the topic owner.
- Some annotations are generated **automatically** on topic updates (e.g., recaps).
- Others can be **manually added** via UI.
- Annotation generation is handled by **Celery background tasks**.
- Community suggestions for annotations are possible.

### 4. Collaboration Model

Inspired by Git-style collaboration, adapted for non-technical users.

#### Workflow

- A user creates a topic.
- Other users can **fork** the topic and modify associated content.
- Forks can be submitted as **update suggestions**.
- Topic owners can:
  - Accept or reject the update
  - Merge parts or all of the contribution
  - Add contributor credits
- Forks can **sync** updates from the original topic.
- MVP does **not** include diff/compare UI.

### 5. Opinions and Comments

Users can contribute by commenting on:

- Individual content items
- Annotations
- Entire topics

Topic owners may choose to **accept** user comments into the topic display.

---

## User Roles

- **Anonymous Visitors**:
  - Browse and view topics and their content

- **Registered Users**:
  - Create topics
  - Add content to topics
  - Add or remove annotations
  - Fork topics and suggest updates
  - Comment on content and annotations

- **Topic Owners**:
  - Moderate contributions
  - Accept/merge suggestions
  - Enable/disable annotations
  - Manage topic status (draft/published)

---

## MVP Scope

- User registration and profiles
- Topic creation with draft/publish flow
- Globally unique content model
- Manual content addition and periodic fetching from predefined sources
- Basic annotation engine (recap + timeline)
- Background job processing via Celery
- Fork and suggest update flow (no comparison UI)
- Commenting on topics, content, and annotations
- AI-based moderation for content and suggestions

---
