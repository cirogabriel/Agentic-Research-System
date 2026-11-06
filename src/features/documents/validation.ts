import { ALLOWED_EXTENSIONS } from '@/types/api'
import { formatBytes } from '@/utils/format'

export const DEFAULT_MAX_UPLOAD_MB = 25

export function extensionOf(name: string): string {
  const i = name.lastIndexOf('.')
  return i === -1 ? '' : name.slice(i).toLowerCase()
}

/** Valida extensión y tamaño antes de enviar. El backend repite estas validaciones (y comprueba el contenido real). */
export function validateFile(file: Pick<File, 'name' | 'size'>, maxMb: number = DEFAULT_MAX_UPLOAD_MB): string | null {
  const ext = extensionOf(file.name)
  if (!(ALLOWED_EXTENSIONS as readonly string[]).includes(ext)) return `Formato no admitido (${ext || 'sin extensión'}). Admitidos: PDF, DOCX, TXT, Markdown y HTML.`
  if (file.size === 0) return 'El archivo está vacío.'
  if (file.size > maxMb * 1024 * 1024) return `Supera el límite de ${maxMb} MB (${formatBytes(file.size)}).`
  return null
}
