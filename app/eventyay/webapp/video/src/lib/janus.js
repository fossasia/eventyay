// Thin wrapper to make janus-gateway available as an ES module default export.
// Vite keeps the package's browser script module-scoped, so do not rely on
// window.Janus being populated as the old webpack exports-loader setup did.
import JanusGateway from '../shims/janus-gateway'

const Janus = JanusGateway?.default || JanusGateway || (
	typeof window !== 'undefined' ? window.Janus : undefined
)

export default Janus
