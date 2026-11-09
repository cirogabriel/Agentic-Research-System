import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => cleanup());

Element.prototype.scrollIntoView = function scrollIntoView() {};
Element.prototype.scrollTo =
  function scrollTo() {} as typeof Element.prototype.scrollTo;
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as { ResizeObserver?: unknown }).ResizeObserver ??=
  ResizeObserverStub;
