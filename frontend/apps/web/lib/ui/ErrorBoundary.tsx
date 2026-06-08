'use client';

import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Rendered when a child throws. Receives the error and a reset callback. */
  fallback: (error: Error, reset: () => void) => ReactNode;
  /** Optional hook for logging/telemetry. */
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Generic React error boundary.
 *
 * Stops a render-time exception in a subtree from white-screening the whole
 * app ("Application error: a client-side exception has occurred"). The subtree
 * is replaced by `fallback`, which gets a `reset` to attempt re-rendering.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    this.props.onError?.(error, info);
  }

  reset = () => this.setState({ error: null });

  override render() {
    if (this.state.error) return this.props.fallback(this.state.error, this.reset);
    return this.props.children;
  }
}
