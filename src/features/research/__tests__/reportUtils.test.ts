import { describe, expect, it } from 'vitest';
import {
  linkifyCitations,
  sectionKind,
  splitReportSections,
} from '../reportUtils';

const MD = `# Terremotos en los Andes

## Resumen ejecutivo
La subducción de Nazca [S1].

## Metodología utilizada
Se realizaron 2 iteraciones.

## Desarrollo de los hallazgos
### Causas
Texto

\`\`\`
## no es un encabezado
\`\`\`

## Referencias propias
- **[S1]** doc.pdf, pág. 2

## Conclusiones
- Una
`;

describe('splitReportSections', () => {
  const { title, sections } = splitReportSections(MD);
  it('extrae el título y las secciones de nivel 2', () => {
    expect(title).toBe('Terremotos en los Andes');
    expect(sections.map((s) => s.heading)).toEqual([
      'Resumen ejecutivo',
      'Metodología utilizada',
      'Desarrollo de los hallazgos',
      'Referencias propias',
      'Conclusiones',
    ]);
  });
  it('clasifica por los encabezados reales del backend', () => {
    expect(sections.map((s) => s.kind)).toEqual([
      'summary',
      'method',
      'findings',
      'other',
      'conclusions',
    ]);
    expect(sectionKind('Executive summary')).toBe('summary');
    expect(sectionKind('Limitations')).toBe('limits');
  });
  it('mantiene subsecciones y no corta en bloques de código', () => {
    expect(sections[2]!.body).toContain('### Causas');
    expect(sections[2]!.body).toContain('## no es un encabezado');
  });
});

describe('linkifyCitations', () => {
  it('convierte etiquetas en enlaces internos', () => {
    expect(linkifyCitations('Dato [S1, S2].')).toBe(
      'Dato [\\[S1\\]](#src-S1) [\\[S2\\]](#src-S2).',
    );
  });
  it('no modifica bloques de código', () => {
    const md = 'x\n```\n[S1]\n```\ny [S3]';
    const out = linkifyCitations(md);
    expect(out).toContain('```\n[S1]\n```');
    expect(out).toContain('(#src-S3)');
  });
});
