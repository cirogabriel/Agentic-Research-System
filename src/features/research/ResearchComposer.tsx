import { useState } from 'react';
import { Paperclip, SlidersHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useConfiguration } from '@/features/settings/queries';
import {
  usePreferencesStore,
  type ResearchDefaults,
} from '@/stores/preferencesStore';
import type { ResearchOptions } from '@/types/api';
import { cn } from '@/utils/cn';
import { DocumentScope } from './DocumentScope';
import { OptionsForm } from './OptionsForm';
import {
  buildOptions,
  QUERY_MAX,
  validateDefaults,
  validateQuery,
} from './options';

interface Props {
  placeholder: string;
  submitLabel?: string;
  pending?: boolean;
  disabledReason?: string;
  onSubmit: (query: string, options: ResearchOptions) => void;
  autoFocus?: boolean;
}

export function ResearchComposer({
  placeholder,
  submitLabel = 'Enviar',
  pending,
  disabledReason,
  onSubmit,
  autoFocus,
}: Props) {
  const [query, setQuery] = useState('');
  const [touched, setTouched] = useState(false);
  const [panel, setPanel] = useState<'scope' | 'options' | null>(null);
  const [docIds, setDocIds] = useState<string[]>([]);
  const storedDefaults = usePreferencesStore((s) => s.defaults);
  const [local, setLocal] = useState<ResearchDefaults>(storedDefaults);
  const config = useConfiguration();
  const disabled = !!disabledReason || !!pending;
  const queryError = touched ? validateQuery(query) : null;
  const optionErrors = validateDefaults(local);
  const canSend =
    !disabled &&
    validateQuery(query) === null &&
    Object.keys(optionErrors).length === 0;

  const submit = () => {
    setTouched(true);
    if (!canSend) return;
    onSubmit(query.trim(), buildOptions(local, docIds));
    setQuery('');
    setTouched(false);
  };

  return (
    <div className="composer-wrap">
      <div className={cn('composer', disabled && 'is-disabled')}>
        <textarea
          value={query}
          autoFocus={autoFocus}
          disabled={disabled}
          onChange={(e) => setQuery(e.target.value)}
          onBlur={() => query && setTouched(true)}
          onKeyDown={(e) => {
            if (
              e.key === 'Enter' &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing &&
              e.keyCode !== 229
            ) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={disabledReason ?? placeholder}
          aria-label="Escribe una pregunta de investigación"
          aria-invalid={!!queryError}
          maxLength={QUERY_MAX + 200}
          rows={2}
        />
        {queryError && (
          <p className="field-error" role="alert">
            {queryError}
          </p>
        )}
        {panel && (
          <div
            style={{
              margin: '8px 0 10px',
              paddingTop: 10,
              borderTop: '1px solid #efeff2',
            }}
          >
            {panel === 'scope' ? (
              <DocumentScope selected={docIds} onChange={setDocIds} />
            ) : (
              <OptionsForm
                value={local}
                onChange={setLocal}
                idPrefix="composer"
                backend={{
                  max_iterations: config.data?.max_iterations,
                  token_budget: config.data?.token_budget,
                  retrieval_top_k: config.data?.retrieval_top_k,
                }}
              />
            )}
          </div>
        )}
        <div className="composer-actions">
          <button
            type="button"
            className="icon-button"
            aria-label="Limitar a documentos"
            aria-pressed={panel === 'scope'}
            title="Limitar la búsqueda a documentos concretos"
            onClick={() => setPanel(panel === 'scope' ? null : 'scope')}
            disabled={disabled}
          >
            <Paperclip />
            {docIds.length > 0 && (
              <span
                className="text-[10px] font-semibold"
                style={{ marginLeft: 2 }}
              >
                {docIds.length}
              </span>
            )}
          </button>
          <button
            type="button"
            className="icon-button"
            aria-label="Opciones de investigación"
            aria-pressed={panel === 'options'}
            title="Parámetros de esta investigación"
            onClick={() => setPanel(panel === 'options' ? null : 'options')}
            disabled={disabled}
          >
            <SlidersHorizontal />
          </button>
          <span className="composer-hint">Shift + Enter para nueva línea</span>
          <Button
            onClick={submit}
            disabled={!canSend}
            className="send-button"
            size="sm"
          >
            {pending ? 'Enviando…' : submitLabel} <span>↗</span>
          </Button>
        </div>
      </div>
      <p className="disclaimer">
        La investigación puede contener errores. Revisa siempre las fuentes
        citadas antes de tomar decisiones.
      </p>
    </div>
  );
}
