import type { ReactNode } from 'react';
import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toUserMessage } from '@/services/api';

export function LoadingState({
  label = 'Cargando…',
  rows = 0,
}: {
  label?: string;
  rows?: number;
}) {
  if (rows > 0)
    return (
      <div
        role="status"
        aria-label={label}
        className="stack"
        style={{ gap: 10 }}
      >
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="skeleton" style={{ height: 38 }} />
        ))}
      </div>
    );
  return (
    <div className="state-box" role="status">
      <span className="spinner" />
      <p>{label}</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="state-box">
      <div className="state-icon">{icon ?? <Inbox size={20} />}</div>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  title = 'No se pudo cargar la información',
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div className="state-box" role="alert">
      <div className="state-icon error">
        <AlertTriangle size={20} />
      </div>
      <h3>{title}</h3>
      <p>{toUserMessage(error)}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw /> Reintentar
        </Button>
      )}
    </div>
  );
}


export function QueryBoundary({
  isLoading,
  error,
  isEmpty,
  onRetry,
  children,
  loadingRows = 4,
  empty,
}: {
  isLoading: boolean;
  error: unknown;
  isEmpty?: boolean;
  onRetry?: () => void;
  children: ReactNode;
  loadingRows?: number;
  empty?: ReactNode;
}) {
  if (isLoading)
    return <LoadingState rows={loadingRows} label="Cargando datos" />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (isEmpty) return <>{empty}</>;
  return <>{children}</>;
}
