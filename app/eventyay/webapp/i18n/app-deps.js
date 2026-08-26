import {createRequire} from 'node:module'
import path from 'node:path'
import {pathToFileURL} from 'node:url'

const require = createRequire(path.resolve(process.cwd(), 'package.json'))

export async function importFromApp(specifier) {
	return import(pathToFileURL(require.resolve(specifier)).href)
}
