/**
 * Attach listeners for one or multiple events to an element and return a
 * function that removes the listeners.
 *
 * @param {Element} element
 * @param {string[]} events
 * @param {(event: Event) => any} listener
 * @param {Object} options
 * @param {boolean} [options.useCapture]
 * @return {function} Function which removes the event listeners.
 */
export function listen(element, events, listener, { useCapture = false } = {}) {
  if (!Array.isArray(events)) {
    events = [events];
  }
  events.forEach(event =>
    element.addEventListener(event, listener, useCapture)
  );
  return () => {
    events.forEach(event =>
      element.removeEventListener(event, listener, useCapture)
    );
  };
}
