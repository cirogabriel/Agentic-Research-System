import { useNavigate } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { ResearchComposer } from '@/features/research/ResearchComposer';
import { useCreateResearch } from '@/features/research/queries';
import { notify } from '@/stores/toastStore';

export function NewResearchPage() {
  const navigate = useNavigate();
  const create = useCreateResearch();
  return (
    <div className="page" style={{ maxWidth: 820 }}>
      <div className="empty-hero">
        <div className="state-icon">
          <Sparkles size={20} />
        </div>
        <p className="eyebrow">Nueva investigación</p>
        <h1>¿Qué quieres investigar?</h1>
        <p className="muted-copy" style={{ maxWidth: 520, lineHeight: 1.6 }}>
          El Supervisor planificará subtareas, los agentes buscarán en tus
          documentos indexados, analizarán y verificarán la evidencia y
          recibirás un informe con referencias.
        </p>
      </div>
      <ResearchComposer
        autoFocus
        pending={create.isPending}
        submitLabel="Investigar"
        placeholder="Ej.: Investiga las principales causas de los terremotos en los Andes y compara las explicaciones científicas."
        onSubmit={(query, options) =>
          create.mutate(
            { query, options },
            {
              onSuccess: (r) => {
                notify.success('Investigación iniciada');
                navigate(`/research/${r.id}`);
              },
            },
          )/* cuerpo no JSON */
        }
      />
    </div>
  );
}
