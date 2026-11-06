const FRAME_PREFIX_LENGTH = 5
const PROTOCOL_VERSION = 1

export function parseTtsFrame(buffer) {
	if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < FRAME_PREFIX_LENGTH) {
		throw new Error('TTS frame is too short')
	}

	const view = new DataView(buffer)
	const version = view.getUint8(0)
	if (version !== PROTOCOL_VERSION) {
		throw new Error(`Unsupported TTS protocol version: ${version}`)
	}

	const headerLength = view.getUint32(1, false)
	if (buffer.byteLength < FRAME_PREFIX_LENGTH + headerLength) {
		throw new Error('TTS frame is truncated')
	}

	const headerBytes = new Uint8Array(buffer, FRAME_PREFIX_LENGTH, headerLength)
	let header
	try {
		header = JSON.parse(new TextDecoder('utf-8').decode(headerBytes))
	} catch (error) {
		throw new Error(`Invalid TTS frame header: ${error.message}`)
	}

	return {
		header,
		audioBytes: new Uint8Array(buffer, FRAME_PREFIX_LENGTH + headerLength),
	}
}
