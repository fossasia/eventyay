export const TTS_PROTOCOL_VERSION = 1;
// Voxbento synthesises 16-bit little-endian mono PCM at 24 kHz.
export const TTS_DEFAULT_SAMPLE_RATE = 24000;

const PREAMBLE_LENGTH = 5;

/**
 * Parses one Voxbento TTS frame.
 *
 * Wire format, packed server-side with struct.pack('>BI', 1, len(header)):
 *   [1-byte version][4-byte big-endian JSON header length][JSON header][PCM audio bytes]
 *
 * WebSocket messages are delimited by the protocol, so each binary message
 * carries exactly one frame; everything after the header is audio.
 */
export function parseTtsFrame(buffer) {
	if (!(buffer instanceof ArrayBuffer)) {
		throw new TypeError('TTS frame must be an ArrayBuffer');
	}
	if (buffer.byteLength < PREAMBLE_LENGTH) {
		throw new Error('TTS frame too short');
	}

	const view = new DataView(buffer);
	const version = view.getUint8(0);
	if (version !== TTS_PROTOCOL_VERSION) {
		throw new Error(`Unsupported TTS protocol version: ${version}`);
	}

	const headerLength = view.getUint32(1, false);
	if (buffer.byteLength < PREAMBLE_LENGTH + headerLength) {
		throw new Error('TTS frame truncated');
	}

	const headerBytes = new Uint8Array(buffer, PREAMBLE_LENGTH, headerLength);
	const header = JSON.parse(new TextDecoder('utf-8').decode(headerBytes));
	const audioBytes = new Uint8Array(buffer, PREAMBLE_LENGTH + headerLength);

	return { header, audioBytes };
}

/**
 * Converts 16-bit little-endian PCM into Web Audio float samples in [-1, 1).
 * A trailing odd byte, which cannot form a sample, is ignored.
 */
export function pcm16ToFloat32(audioBytes) {
	const sampleCount = Math.floor(audioBytes.byteLength / 2);
	const view = new DataView(audioBytes.buffer, audioBytes.byteOffset, sampleCount * 2);
	const samples = new Float32Array(sampleCount);
	for (let i = 0; i < sampleCount; i++) {
		samples[i] = view.getInt16(i * 2, true) / 32768;
	}
	return samples;
}
