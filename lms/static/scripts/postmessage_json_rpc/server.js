/**
 * See https://www.jsonrpc.org/specification#request_object.
 *
 * @typedef JsonRpcRequest
 * @prop {'2.0'} jsonrpc
 * @prop {string} method
 * @prop {unknown[]} params
 * @prop {string|null} id
 *
 * @typedef {Omit<JsonRpcRequest, 'id'>} JsonRpcNotification
 */

/**
 * See https://www.jsonrpc.org/specification#response_object
 *
 * @typedef JsonRpcResponse
 * @prop {'2.0'} jsonrpc
 * @prop {object} [result]
 * @prop {JsonRpcError} [error]
 * @prop {string|null} id
 */

/**
 * See https://www.jsonrpc.org/specification#error_object
 *
 * @typedef JsonRpcError
 * @prop {number} code
 * @prop {string} message
 * @prop {object} [data]
 */

/**
 * @typedef {(...args: any[]) => any|Promise<any>} RpcMethod
 */

/**
 * A JSON-RPC-over-postMessage server.
 *
 * After constructing a server you have to call its register() method to
 * register remotely callable methods. After a method has been registered the
 * server will respond to remote requests for that method by caling the method
 * and sending the method's return value, serialized to a JSON string, back to
 * the caller over postMessage. For example:
 *
 *     const server = new Server(['https://hypothes.is']);
 *     server.register('requestConfig', requestConfig);
 */
export class Server {
  /**
   * @param {string[]} allowedOrigins -
   *   Specifies the origins of iframes that may send requests to this server
   *   via `window.postMessage`.
   */
  constructor(allowedOrigins) {
    this._allowedOrigins = allowedOrigins;

    // Add a postMessage event listener so we can recieve JSON-RPC requests.
    this._boundReceiveMessage = this._receiveMessage.bind(this);
    window.addEventListener('message', this._boundReceiveMessage);

    /**
     * The methods that can be called remotely via this server.
     * @type {Record<string,RpcMethod>}
     */
    this._registeredMethods = {};

    /**
     * Promise that resolves with a reference to the Hypothesis client's sidebar
     * iframe.
     *
     * @type {Promise<{ frame: Window, origin: string }>}
     */
    this.sidebarWindow = new Promise(resolve => {
      this._resolveSidebarWindow = resolve;
    });
  }

  /**
   * Register a remotely callable method with this server.
   *
   * @param {string} name
   * @param {RpcMethod} method
   */
  register(name, method) {
    this._registeredMethods[name] = method;
  }

  /**
   * Turn off this Server instance, it will no longer respond to messages.
   */
  off() {
    window.removeEventListener('message', this._boundReceiveMessage);
  }

  /**
   * Receive a JSON-RPC-postMessage request and respond to it.
   *
   * Receive a postMessage event and, if it's a JSON-RPC request from an
   * allowed origin, post back either a result or an error response.
   *
   * @param {MessageEvent} event
   */
  async _receiveMessage(event) {
    if (!this._allowedOrigins.includes(event.origin)) {
      return;
    }

    if (!this._isJSONRPCRequest(event.data)) {
      return;
    }

    // Resolve the promise we created in the constructor with the saved
    // sidebar frame and origin.
    this._resolveSidebarWindow({
      frame: /** @type {Window} */ (event.source),
      origin: event.origin,
    });

    if (typeof event.data.id === 'undefined') {
      // The absence of an `id` property indicates a JSON-RPC 2.0 Notification
      // request object, which should not get a response.
      this._jsonRPCNotification(event.data);
      return;
    }

    const result = await this._jsonRPCResponse(event.data);
    /** @type {WindowProxy} */ (event.source).postMessage(result, event.origin);
  }

  /**
   * Invoke the method indicated in the JSON-RPC 2.0 notification request
   * object.
   *
   * @param {JsonRpcNotification} request
   */
  async _jsonRPCNotification(request) {
    const method = this._registeredMethods[request.method];

    if (!method) {
      console.error(
        `Received JSON-RPC notification for unrecognized method: ${request.method}`
      );
      return;
    }

    try {
      await method(...(request.params ?? []));
    } catch (e) {
      console.error(`JSON-RPC notification method failed: ${e}`);
    }
  }

  /**
   * Return true if the provided object is a JSON-RPC request.
   *
   * @param {any} request
   */
  _isJSONRPCRequest(request) {
    if (!(request instanceof Object) || request.jsonrpc !== '2.0') {
      // Event is neither a JSON-RPC request or response.
      return false;
    }

    if (request.result || request.error) {
      // Event is a JSON-RPC _response_, rather than a request.
      return false;
    }

    return true;
  }

  /**
   * Return a JSON-RPC response object for the given JSON-RPC request object.
   *
   * @param {JsonRpcRequest} request
   * @return {Promise<JsonRpcResponse>}
   */
  async _jsonRPCResponse(request) {
    // Return an error response if the request id is invalid.
    // id must be a string, number or null.
    const id = request.id;
    if (!(['string', 'number'].includes(typeof id) || id === null)) {
      return {
        jsonrpc: '2.0',
        id: null,
        error: { code: -32600, message: 'request id invalid' },
      };
    }

    const method = this._registeredMethods[request.method];

    // Return an error response if the method name is invalid.
    if (method === undefined) {
      return {
        jsonrpc: '2.0',
        id: request.id,
        error: { code: -32600, message: 'method name not recognized' },
      };
    }

    // Call the method and return the result response.
    try {
      const result = await method(...(request.params ?? []));
      return { jsonrpc: '2.0', result: result, id: request.id };
    } catch (e) {
      return {
        jsonrpc: '2.0',
        id: request.id,
        error: { code: -32600, message: e.message },
      };
    }
  }
}
