(function () {
  class WidgetControllerRegistry {
    constructor() {
      this.controllers = new Map();
    }

    register(key, factory) {
      if (!key || typeof key !== 'string') {
        return;
      }
      const normalizedKey = key.trim().toLowerCase();
      if (!normalizedKey) {
        return;
      }
      this.controllers.set(normalizedKey, factory);
    }

    init(key, context) {
      if (!key) return null;
      const normalizedKey = String(key).trim().toLowerCase();
      const factory = this.controllers.get(normalizedKey);
      if (!factory) {
        return null;
      }
      try {
        return factory(context) || null;
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Failed to initialise widget controller', normalizedKey, error);
        return null;
      }
    }
  }

  if (!window.TopicWidgetRegistry) {
    window.TopicWidgetRegistry = new WidgetControllerRegistry();
  }
}());
