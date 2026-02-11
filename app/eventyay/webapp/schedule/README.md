# pretalx-schedule

## Project setup
```
npm ci
```

### Compiles and hot-reloads for development
```
npm start
```

### Compiles and minifies for production
```
npm run build
```

### Build for pretalx (web component)

Make sure the `schedule` and `pretalx` repositories share a root directory, then simply run

```
./update.sh
```

### Release library to npm

```sh
npm version minor|patch
npm publish --access=public
```

### Lints and fixes files
```
npm run lint
```
