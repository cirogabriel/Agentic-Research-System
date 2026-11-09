import { useState } from 'react';
import { RefreshCw, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ConfirmDialog, Modal } from '@/components/common/Modal';
import { StatusBadge } from '@/components/common/StatusBadge';
import { ErrorState, LoadingState } from '@/components/common/States';
import {
  formatBytes,
  formatDateTime,
  documentStatusMeta,
  truncate,
} from '@/utils/format';
import { useDeleteDocument, useDocument, useReindexDocument } from './queries';

export function DocumentDrawer({
  id,
  onClose,
}: {
  id: string;
  onClose: () => void;
}) {
  const { data: d, isLoading, error, refetch } = useDocument(id);
  const reindex = useReindexDocument();
  const del = useDeleteDocument();
  const [confirm, setConfirm] = useState(false);
  return (
    <>
      <Modal side title="Detalle del documento" onClose={onClose}>
        {isLoading && <LoadingState label="Cargando" rows={5} />}
        {error && <ErrorState error={error} onRetry={() => void refetch()} />}
        {d && (
          <>
            <div className="row" style={{ marginBottom: 14 }}>
              <strong style={{ overflowWrap: 'anywhere' }}>
                {d.title ?? d.filename}
              </strong>
              <span className="spacer">
                <StatusBadge meta={documentStatusMeta(d.status)} />
              </span>
            </div>
            {d.status === 'failed' && d.error && (
              <div
                className="banner error"
                role="alert"
                style={{ marginBottom: 14 }}
              >
                {truncate(d.error, 300)}
              </div>
            )}
            <dl className="kv">
              <dt>Archivo</dt>
              <dd>{d.filename}</dd>
              <dt>Tipo</dt>
              <dd>{d.file_type.toUpperCase()}</dd>
              <dt>Autor</dt>
              <dd>{d.author ?? '—'}</dd>
              <dt>Fecha del documento</dt>
              <dd>{d.document_date ?? '—'}</dd>
              <dt>Tamaño</dt>
              <dd>{formatBytes(d.size_bytes)}</dd>
              <dt>Páginas</dt>
              <dd>{d.num_pages ?? '—'}</dd>
              <dt>Fragmentos (chunks)</dt>
              <dd>{d.num_chunks}</dd>
              <dt>Versión</dt>
              <dd>{d.version}</dd>
              <dt>Subido</dt>
              <dd>{formatDateTime(d.created_at)}</dd>
              <dt>Indexado</dt>
              <dd>{formatDateTime(d.indexed_at)}</dd>
              <dt>Hash</dt>
              <dd className="mono">{d.content_hash.slice(0, 16)}…</dd>
              <dt>ID</dt>
              <dd className="mono">{d.id}</dd>
            </dl>
            <div
              className="modal-actions"
              style={{ justifyContent: 'flex-start', flexWrap: 'wrap' }}
            >
              <Button
                variant="outline"
                size="sm"
                disabled={reindex.isPending || d.status === 'processing'}
                onClick={() => reindex.mutate({ id: d.id, force: false })}
              >
                <RefreshCw /> Reindexar
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={reindex.isPending || d.status === 'processing'}
                onClick={() => reindex.mutate({ id: d.id, force: true })}
              >
                Forzar reindexación
              </Button>
              <Button
                variant="destructive"
                size="sm"
                className="spacer"
                onClick={() => setConfirm(true)}
              >
                <Trash2 /> Eliminar
              </Button>
            </div>
          </>
        )}
      </Modal>
      {confirm && d && (
        <ConfirmDialog
          danger
          title="Eliminar documento"
          confirmLabel="Eliminar"
          busy={del.isPending}
          description={
            <>
              Se eliminará <strong>{d.title ?? d.filename}</strong> junto con
              sus fragmentos y embeddings. Las fuentes de informes ya generados
              dejarán de enlazar a este documento.
            </>
          }
          onClose={() => setConfirm(false)}
          onConfirm={() =>
            del.mutate(d.id, {
              onSuccess: () => {
                setConfirm(false);
                onClose();
              },
            })
          }
        />
      )}
    </>
  );
}
