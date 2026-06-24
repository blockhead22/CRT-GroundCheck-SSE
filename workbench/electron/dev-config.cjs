const path = require('node:path')

function devUserDataPath(app) {
  return path.join(app.getPath('temp'), 'aether-workbench-dev')
}

function configureDevUserData(app, env = process.env) {
  if (env.NODE_ENV !== 'development') return null
  const userDataPath = devUserDataPath(app)
  app.setPath('userData', userDataPath)
  return userDataPath
}

module.exports = { configureDevUserData, devUserDataPath }
