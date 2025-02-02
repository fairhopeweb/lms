// Expose sinon assertions.
sinon.assert.expose(assert, { prefix: null });

// Configure Enzyme for UI tests.
import 'preact/debug';

import { configure } from 'enzyme';
import { Adapter } from 'enzyme-adapter-preact-pure';
configure({ adapter: new Adapter() });

// Register the same set of icons that is available in the app.
import { registerIcons } from '@hypothesis/frontend-shared';
import iconSet from './frontend_apps/icons';

registerIcons(iconSet);

// Ensure that uncaught exceptions between tests result in the tests failing.
// This works around an issue with mocha / karma-mocha, see
// https://github.com/hypothesis/client/issues/2249.
let pendingError = null;
let pendingErrorNotice = null;

/* istanbul ignore next */
window.addEventListener('error', event => {
  pendingError = event.error;
  pendingErrorNotice = 'An uncaught exception was thrown between tests';
});
/* istanbul ignore next */
window.addEventListener('unhandledrejection', event => {
  pendingError = event.reason;
  pendingErrorNotice = 'An uncaught promise rejection occurred between tests';
});

afterEach(() => {
  /* istanbul ignore if */
  if (pendingError) {
    console.error(pendingErrorNotice);
    throw pendingError;
  }
});
