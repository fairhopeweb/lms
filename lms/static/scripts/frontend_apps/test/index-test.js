import { Config } from '../config';
import { init, $imports } from '../index';
import { Services } from '../services';

// Minimal version of the configuration that the backend renders into the page.
const minimalConfig = {
  api: {
    authToken: '1234',
  },
  rpcServer: {
    allowedOrigins: ['https://example.com'],
  },
  mode: 'basic-lti-launch',
};

describe('LMS frontend entry', () => {
  let container;
  let fakeContentInfoFetcher;
  let fakeReadConfig;

  beforeEach(() => {
    container = document.createElement('div');
    container.id = 'app';
    document.body.append(container);

    fakeContentInfoFetcher = {
      fetch: sinon.stub(),
    };
    fakeReadConfig = sinon.stub().returns(minimalConfig);

    $imports.$mock({
      './config': { readConfig: fakeReadConfig, Config },

      // Since `init` calls `render` directly, mock these components in a way
      // that allows us to tell what was rendered by inspecting the DOM,
      // as opposed to querying an Enzyme wrapper.
      './components/BasicLTILaunchApp': () => (
        <div data-component="BasicLTILaunchApp" />
      ),
      './components/OAuth2RedirectErrorApp': () => (
        <div data-component="OAuth2RedirectErrorApp" />
      ),
      './components/ErrorDialogApp': () => (
        <div data-component="ErrorDialogApp" />
      ),
      './components/FilePickerApp': () => (
        <div data-component="FilePickerApp" />
      ),

      './services': {
        ClientRPC: sinon.stub(),
        ContentInfoFetcher: sinon.stub().returns(fakeContentInfoFetcher),
        GradingService: sinon.stub(),
        Services,
        VitalSourceService: sinon.stub(),
      },
    });
  });

  afterEach(() => {
    container.remove();
    $imports.$restore();
  });

  [
    {
      config: { mode: 'basic-lti-launch' },
      appComponent: 'BasicLTILaunchApp',
    },
    {
      config: { mode: 'content-item-selection' },
      appComponent: 'FilePickerApp',
    },
    {
      config: { mode: 'error-dialog' },
      appComponent: 'ErrorDialogApp',
    },
    {
      config: { mode: 'oauth2-redirect-error' },
      appComponent: 'OAuth2RedirectErrorApp',
    },
  ].forEach(({ config, appComponent }) => {
    it('launches correct app for "mode" config', () => {
      fakeReadConfig.returns({ ...minimalConfig, ...config });

      init();

      assert.ok(container.querySelector(`[data-component=${appComponent}`));
    });
  });

  it('console logs debug values', () => {
    const log = sinon.stub(console, 'log');

    try {
      fakeReadConfig.returns({
        ...minimalConfig,
        debug: { values: { key: 'value' } },
      });

      init();

      assert.calledWith(log, 'key: value');
    } finally {
      log.restore();
    }
  });

  describe('LTI launch', () => {
    it('fetches data for content banner, if configured', () => {
      const contentBanner = { source: 'jstor', itemId: '12345' };
      fakeReadConfig.returns({ ...minimalConfig, contentBanner });

      init();

      assert.calledWith(fakeContentInfoFetcher.fetch, contentBanner);
    });
  });
});
