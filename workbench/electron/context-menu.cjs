const MAX_SPELLING_SUGGESTIONS = 6

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function canEdit(params, flag) {
  return Boolean(params?.editFlags?.[flag])
}

function addSpellcheckItems(template, params, webContents) {
  const misspelledWord = hasText(params?.misspelledWord) ? params.misspelledWord.trim() : ''
  if (!misspelledWord) return

  const suggestions = Array.isArray(params.dictionarySuggestions)
    ? params.dictionarySuggestions.filter(hasText).slice(0, MAX_SPELLING_SUGGESTIONS)
    : []

  if (suggestions.length > 0) {
    for (const suggestion of suggestions) {
      template.push({
        label: suggestion,
        click: () => webContents.replaceMisspelling(suggestion),
      })
    }
  } else {
    template.push({
      label: `No spelling suggestions for "${misspelledWord}"`,
      enabled: false,
    })
  }

  const dictionary = webContents?.session
  template.push({
    label: `Add "${misspelledWord}" to dictionary`,
    enabled: Boolean(dictionary?.addWordToSpellCheckerDictionary),
    click: () => dictionary?.addWordToSpellCheckerDictionary?.(misspelledWord),
  })
  template.push({ type: 'separator' })
}

function addEditableItems(template, params) {
  template.push(
    { role: 'undo', enabled: canEdit(params, 'canUndo') },
    { role: 'redo', enabled: canEdit(params, 'canRedo') },
    { type: 'separator' },
    { role: 'cut', enabled: canEdit(params, 'canCut') },
    { role: 'copy', enabled: canEdit(params, 'canCopy') },
    { role: 'paste', enabled: canEdit(params, 'canPaste') },
    { role: 'pasteAndMatchStyle', enabled: canEdit(params, 'canPaste') },
    { type: 'separator' },
    { role: 'selectAll', enabled: canEdit(params, 'canSelectAll') },
  )
}

function buildSpellcheckContextMenuTemplate(params, webContents) {
  const isEditable = Boolean(params?.isEditable)
  const hasSelection = hasText(params?.selectionText)
  if (!isEditable && !hasSelection) return []

  const template = []
  if (isEditable) {
    addSpellcheckItems(template, params, webContents)
    addEditableItems(template, params)
    return template
  }

  return [{ role: 'copy', enabled: hasSelection }]
}

module.exports = {
  MAX_SPELLING_SUGGESTIONS,
  buildSpellcheckContextMenuTemplate,
}
