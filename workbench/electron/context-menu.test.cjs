const test = require('node:test')
const assert = require('node:assert/strict')
const { buildSpellcheckContextMenuTemplate } = require('./context-menu.cjs')

function editableParams(overrides = {}) {
  return {
    isEditable: true,
    selectionText: '',
    misspelledWord: '',
    dictionarySuggestions: [],
    editFlags: {
      canUndo: true,
      canRedo: false,
      canCut: true,
      canCopy: true,
      canPaste: true,
      canSelectAll: true,
    },
    ...overrides,
  }
}

test('editable context menu includes spelling suggestions and dictionary action', () => {
  const calls = []
  const webContents = {
    replaceMisspelling: (word) => calls.push(['replace', word]),
    session: {
      addWordToSpellCheckerDictionary: (word) => calls.push(['dictionary', word]),
    },
  }

  const menu = buildSpellcheckContextMenuTemplate(
    editableParams({
      misspelledWord: 'mispelled',
      dictionarySuggestions: ['misspelled', 'dispelled'],
    }),
    webContents,
  )

  assert.equal(menu[0].label, 'misspelled')
  assert.equal(menu[1].label, 'dispelled')
  assert.equal(menu[2].label, 'Add "mispelled" to dictionary')

  menu[0].click()
  menu[2].click()

  assert.deepEqual(calls, [
    ['replace', 'misspelled'],
    ['dictionary', 'mispelled'],
  ])
})

test('editable context menu includes normal edit roles', () => {
  const menu = buildSpellcheckContextMenuTemplate(editableParams(), {})
  const roles = menu.filter((item) => item.role).map((item) => [item.role, item.enabled])

  assert.deepEqual(roles, [
    ['undo', true],
    ['redo', false],
    ['cut', true],
    ['copy', true],
    ['paste', true],
    ['pasteAndMatchStyle', true],
    ['selectAll', true],
  ])
})

test('non-editable selected text only gets copy', () => {
  const menu = buildSpellcheckContextMenuTemplate(
    { isEditable: false, selectionText: 'selected text' },
    {},
  )

  assert.deepEqual(menu, [{ role: 'copy', enabled: true }])
})

test('non-editable empty target has no custom context menu', () => {
  assert.deepEqual(
    buildSpellcheckContextMenuTemplate({ isEditable: false, selectionText: '' }, {}),
    [],
  )
})
