import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders, makeDocument } from '@/test/utils';
import { DocumentsPage } from '@/pages/DocumentsPage';
import { validateFile } from '../validation';
import { ApiError } from '@/services/api';

vi.mock('@/services/documents', () => ({
  documentsService: {
    list: vi.fn(),
    get: vi.fn(),
    upload: vi.fn(),
    remove: vi.fn(),
    reindex: vi.fn(),
  },
}));
vi.mock('@/services/system', () => ({
  systemService: {
    configuration: vi.fn().mockResolvedValue({ max_upload_mb: 1 }),
    health: vi.fn(),
  },
}));
import { documentsService } from '@/services/documents';

const list = (items = [makeDocument()]) =>
  vi
    .mocked(documentsService.list)
    .mockResolvedValue({ items, total: items.length });
beforeEach(() => {
  vi.clearAllMocks();
  list();
});

describe('validateFile', () => {
  it('acepta los formatos del backend y rechaza el resto', () => {
    for (const n of [
      'a.pdf',
      'a.DOCX',
      'a.txt',
      'a.md',
      'a.markdown',
      'a.html',
      'a.htm',
    ])
      expect(validateFile({ name: n, size: 10 })).toBeNull();
    expect(validateFile({ name: 'a.exe', size: 10 })).toMatch(/no admitido/);
    expect(validateFile({ name: 'sin-extension', size: 10 })).toMatch(
      /no admitido/,
    );
  });
  it('valida tamaño y archivos vacíos', () => {
    expect(validateFile({ name: 'a.pdf', size: 26 * 1024 * 1024 })).toMatch(
      /25 MB/,
    );
    expect(validateFile({ name: 'a.pdf', size: 0 })).toMatch(/vacío/);
  });
});

describe('DocumentsPage', () => {
  it('lista documentos con los estados reales del backend', async () => {
    list([
      makeDocument({
        id: 'a',
        filename: 'a.pdf',
        title: null,
        status: 'indexed',
      }),
      makeDocument({
        id: 'b',
        filename: 'b.md',
        title: null,
        file_type: 'md',
        status: 'processing',
      }),
      makeDocument({
        id: 'c',
        filename: 'c.txt',
        title: null,
        file_type: 'txt',
        status: 'failed',
      }),
    ]);
    renderWithProviders(<DocumentsPage />);
    expect(await screen.findByText('Indexado')).toBeInTheDocument();
    expect(screen.getByText('Procesando')).toBeInTheDocument();
    expect(screen.getByText('Fallido')).toBeInTheDocument();
  });

  it('estado vacío cuando no hay documentos', async () => {
    list([]);
    renderWithProviders(<DocumentsPage />);
    expect(
      await screen.findByText('Aún no hay documentos'),
    ).toBeInTheDocument();
  });

  it('estado de error con reintento', async () => {
    vi.mocked(documentsService.list)
      .mockRejectedValueOnce(
        new ApiError('network', 'No se pudo conectar con el backend.'),
      )
      .mockResolvedValue({ items: [makeDocument()], total: 1 });
    renderWithProviders(<DocumentsPage />);
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/No se pudo conectar con el backend/);
    await userEvent.click(
      within(alert).getByRole('button', { name: /reintentar/i }),
    );
    expect(
      await screen.findByText('Seismicity and the Andes'),
    ).toBeInTheDocument();
  });

  it('rechaza formatos y tamaños inválidos sin llamar al backend', async () => {
    const user = userEvent.setup({ applyAccept: false });
    renderWithProviders(<DocumentsPage />);
    await screen.findByText('Seismicity and the Andes');
    const input = screen.getByTestId('file-input');
    await user.upload(input, new File(['x'], 'virus.exe'));
    expect(await screen.findByText(/Formato no admitido/)).toBeInTheDocument();
    await user.upload(
      input,
      new File([new Uint8Array(2 * 1024 * 1024)], 'grande.pdf'),
    );
    expect(
      await screen.findByText(/Supera el límite de 1 MB/),
    ).toBeInTheDocument();
    expect(documentsService.upload).not.toHaveBeenCalled();
  });

  it('sube un archivo válido y muestra el resultado; avisa de duplicados', async () => {
    vi.mocked(documentsService.upload)
      .mockResolvedValueOnce({ document: makeDocument(), action: 'created' })
      .mockResolvedValueOnce({ document: makeDocument(), action: 'duplicate' });
    renderWithProviders(<DocumentsPage />);
    await screen.findByText('Seismicity and the Andes');
    const input = screen.getByTestId('file-input');
    await userEvent.upload(
      input,
      new File(['hola'], 'nota.txt', { type: 'text/plain' }),
    );
    expect(await screen.findByText('Subido. Indexando…')).toBeInTheDocument();
    expect(documentsService.upload).toHaveBeenCalledTimes(1);
    await userEvent.upload(
      input,
      new File(['hola'], 'nota2.txt', { type: 'text/plain' }),
    );
    expect(
      await screen.findByText(/Ya existía un documento idéntico/),
    ).toBeInTheDocument();
  });

  it('muestra el error del backend de una subida fallida', async () => {
    vi.mocked(documentsService.upload).mockRejectedValue(
      new ApiError(
        'validation',
        'El contenido del archivo no coincide con su extensión.',
        422,
      ),
    );
    renderWithProviders(<DocumentsPage />);
    await screen.findByText('Seismicity and the Andes');
    await userEvent.upload(
      screen.getByTestId('file-input'),
      new File(['x'], 'raro.pdf'),
    );
    expect(
      await screen.findByText(/no coincide con su extensión/),
    ).toBeInTheDocument();
  });

  it('abre el detalle y elimina el documento tras confirmar', async () => {
    vi.mocked(documentsService.get).mockResolvedValue(makeDocument());
    vi.mocked(documentsService.remove).mockResolvedValue(undefined);
    renderWithProviders(<DocumentsPage />);
    await userEvent.click(
      await screen.findByRole('row', { name: /ver detalle de andes\.pdf/i }),
    );
    const drawer = await screen.findByRole('dialog', {
      name: /detalle del documento/i,
    });
    expect(await within(drawer).findByText('J. Ramos')).toBeInTheDocument();
    await userEvent.click(
      within(drawer).getByRole('button', { name: /eliminar/i }),
    );
    const confirm = await screen.findByRole('dialog', {
      name: /eliminar documento/i,
    });
    await userEvent.click(
      within(confirm).getByRole('button', { name: 'Eliminar' }),
    );
    await waitFor(() =>
      expect(documentsService.remove).toHaveBeenCalledWith('d1'),
    );
  });
});
