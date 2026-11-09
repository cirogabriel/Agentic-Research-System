import { useRef, useState } from 'react';
import { Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Modal } from '@/components/common/Modal';
import { datasetCreateSchema, type DatasetCreate } from '@/types/api';
import { useCreateDataset } from './queries';


export type ParsedDataset =
  { ok: true; data: DatasetCreate } | { ok: false; error: string };

export function parseDatasetJson(
  text: string,
  fallbackName: string,
): ParsedDataset {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return { ok: false, error: 'El archivo no es un JSON válido.' };
  }
  // Se admite tanto {name, items} como una lista directa de ítems.
  const candidate = Array.isArray(raw)
    ? { name: fallbackName, items: raw }
    : { name: fallbackName, ...(raw as object) };
  const r = datasetCreateSchema.safeParse(candidate);
  if (!r.success) {
    const i = r.error.issues[0];
    return {
      ok: false,
      error: `Formato inválido en "${i?.path.join('.')}": ${i?.message}`,
    };
  }
  return { ok: true, data: r.data };
}

export function DatasetForm({ onClose }: { onClose: () => void }) {
  const create = useCreateDataset();
  const input = useRef<HTMLInputElement>(null);
  const [name, setName] = useState('');
  const [body, setBody] = useState<ParsedDataset | null>(null);
  const [fileName, setFileName] = useState('');
  const onFile = async (f: File | undefined) => {
    if (!f) return;
    setFileName(f.name);
    const parsed = parseDatasetJson(
      await f.text(),
      name || f.name.replace(/\.json$/i, ''),
    );
    setBody(parsed);
    if (parsed.ok && !name) setName(parsed.data.name);
  };
  const ready = body?.ok === true && name.trim().length > 0;
  return (
    <Modal
      title="Nuevo dataset"
      onClose={onClose}
      description="Sube un JSON con los ítems de evaluación (id, question, relevant_documents, reference_answer…)."
    >
      <div className="stack" style={{ gap: 12 }}>
        <div className="field">
          <label htmlFor="ds-name">Nombre</label>
          <input
            id="ds-name"
            className="input"
            value={name}
            maxLength={128}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="field">
          <span className="field-label">Archivo JSON</span>
          <Button variant="outline" onClick={() => input.current?.click()}>
            <Upload /> {fileName || 'Seleccionar archivo'}
          </Button>
          <input
            ref={input}
            hidden
            type="file"
            accept="application/json,.json"
            data-testid="dataset-file"
            onChange={(e) => void onFile(e.target.files?.[0])}
          />
          {body && !body.ok && (
            <span className="field-error" role="alert">
              {body.error}
            </span>
          )}
          {body?.ok && (
            <span className="hint">
              {body.data.items.length} ítem(s) válidos.
            </span>
          )}
        </div>
      </div>
      <div className="modal-actions">
        <Button variant="outline" onClick={onClose}>
          Cancelar
        </Button>
        <Button
          disabled={!ready || create.isPending}
          onClick={() =>
            body?.ok &&
            create.mutate(
              { ...body.data, name: name.trim() },
              { onSuccess: onClose },
            )
          }
        >
          {create.isPending ? 'Creando…' : 'Crear dataset'}
        </Button>
      </div>
    </Modal>
  );
}
