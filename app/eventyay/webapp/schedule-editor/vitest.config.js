import path from 'path'

const dirname = import.meta.dirname

export default {
	resolve: {
		alias: [
			{ find: '~', replacement: path.resolve(dirname, './src') },
			{ find: '@', replacement: path.resolve(dirname, './src') },
		],
	},
	test: {
		environment: 'node',
		include: ['src/**/*.test.ts'],
	},
}
