import { trackEvent } from '../track';

describe('trackEvent', () => {
  // Store original console
  const originalConsole = global.console;
  const originalDev = (global as any).__DEV__;
  const originalEnv = process.env.NODE_ENV;

  beforeEach(() => {
    // Mock console
    global.console = {
      ...originalConsole,
      log: jest.fn(),
    };
  });

  afterEach(() => {
    // Restore console
    global.console = originalConsole;
    (global as any).__DEV__ = originalDev;
    process.env.NODE_ENV = originalEnv;
  });

  it('does not throw on valid input', () => {
    expect(() => {
      trackEvent('test_event', { foo: 'bar' });
    }).not.toThrow();
  });

  it('does not throw on missing params', () => {
    expect(() => {
      trackEvent('test_event');
    }).not.toThrow();
  });

  it('does not throw if console is unavailable', () => {
    // @ts-ignore - intentionally breaking console
    global.console = undefined;

    expect(() => {
      trackEvent('test_event', { foo: 'bar' });
    }).not.toThrow();
  });

  it('does not throw if console.log is missing', () => {
    global.console = {
      ...originalConsole,
      // @ts-ignore - intentionally removing log
      log: undefined,
    };

    expect(() => {
      trackEvent('test_event', { foo: 'bar' });
    }).not.toThrow();
  });

  describe('in development mode', () => {
    beforeEach(() => {
      (global as any).__DEV__ = true;
    });

    it('logs to console with event name and params', () => {
      trackEvent('test_event', { foo: 'bar', baz: 123 });

      expect(console.log).toHaveBeenCalledWith('[Analytics]', 'test_event', {
        foo: 'bar',
        baz: 123,
      });
    });

    it('logs with empty object when params omitted', () => {
      trackEvent('test_event');

      expect(console.log).toHaveBeenCalledWith('[Analytics]', 'test_event', {});
    });
  });

  describe('in production mode', () => {
    beforeEach(() => {
      (global as any).__DEV__ = false;
      process.env.NODE_ENV = 'production';
    });

    it('does not log to console', () => {
      trackEvent('test_event', { foo: 'bar' });

      expect(console.log).not.toHaveBeenCalled();
    });
  });

  describe('edge cases', () => {
    beforeEach(() => {
      (global as any).__DEV__ = true;
    });

    it('handles very long event names', () => {
      const longName = 'a'.repeat(1000);

      expect(() => {
        trackEvent(longName, {});
      }).not.toThrow();

      expect(console.log).toHaveBeenCalled();
    });

    it('handles complex nested params', () => {
      const complexParams = {
        nested: {
          deep: {
            value: 123,
          },
        },
        array: [1, 2, 3],
        nullValue: null,
        undefinedValue: undefined,
      };

      expect(() => {
        trackEvent('complex_event', complexParams);
      }).not.toThrow();

      expect(console.log).toHaveBeenCalledWith('[Analytics]', 'complex_event', complexParams);
    });

    it('handles circular references gracefully', () => {
      const circular: any = { foo: 'bar' };
      circular.self = circular;

      expect(() => {
        trackEvent('circular_event', circular);
      }).not.toThrow();
    });
  });
});
