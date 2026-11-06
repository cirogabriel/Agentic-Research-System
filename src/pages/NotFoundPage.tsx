import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'

export function NotFoundPage() {
  return (
    <div className="placeholder-view">
      <div className="placeholder-icon"><Compass /></div>
      <p className="eyebrow">Error 404</p>
      <h1>Página no encontrada</h1>
      <p className="muted-copy">La dirección que buscas no existe.</p>
      <Link to="/" className="link-accent">Volver al dashboard</Link>
    </div>
  )
}
