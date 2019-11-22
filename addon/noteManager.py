from .constants import MODEL_FIELDS, BASIC_OPTION, EXTRA_OPTION
import logging

logger = logging.getLogger('dict2Anki.noteManager')
try:
    from aqt import mw
    import anki
except ImportError:
    from test.dummy_aqt import mw
    from test import dummy_anki as anki


def getDeckList():
    return [deck['name'] for deck in mw.col.decks.all()]


def getWordsByDeck(deckName) -> [str]:
    notes = mw.col.findNotes(f'deck:"{deckName}"')
    words = []
    for nid in notes:
        note = mw.col.getNote(nid)
        if note.model().get('name', '').lower().startswith('dict2anki') and note['term']:
            words.append(note['term'])
    return words


def getNotes(wordList, deckName) -> list:
    notes = []
    for word in wordList:
        note = mw.col.findNotes(f'deck:"{deckName}" term:"{word}"')
        if note:
            notes.append(note[0])
    return notes


def getOrCreateDeck(deckName):
    deck_id = mw.col.decks.id(deckName)
    deck = mw.col.decks.get(deck_id)
    mw.col.decks.save(deck)
    mw.col.reset()
    mw.reset()
    return deck


def getOrCreateModel(modelName):
    model = mw.col.models.byName(modelName)
    if model:
        if set([f['name'] for f in model['flds']]) == set(MODEL_FIELDS):
            return model
        else:
            logger.warning('模版字段异常，自动删除重建')
            mw.col.models.rem(model)

    logger.info(f'创建新模版:{modelName}')
    newModel = mw.col.models.new(modelName)
    mw.col.models.add(newModel)
    for field in MODEL_FIELDS:
        mw.col.models.addField(newModel, mw.col.models.newField(field))
    mw.col.models.update(newModel)
    return newModel


def getOrCreateModelCardTemplate(modelObject, cardTemplateName):
    logger.info(f'添加卡片类型:{cardTemplateName}')
    existingCardTemplate = modelObject['tmpls']
    if cardTemplateName in [t.get('name') for t in existingCardTemplate]:
        return
    cardTemplate = mw.col.models.newTemplate(cardTemplateName)
    cardTemplate['qfmt'] = '''
        <table>
            <tr>
                <td><h1 class="term">{{term}}</h1><br><div> 英 [{{BrEPhonetic}}] 美 [{{AmEPhonetic}}]</div></div></td>
                <td><img {{image}} height="120px"></td>
            </tr>
        </table>
        <hr>
        释义：
        <div>Tap to View</div>
        {{#phraseFront}}
            <hr style="height:1px;border:none;border-top:1px dashed #0066CC;background-color:#ffffff;">
            短语：
            <ul class='phrase'>{{phraseFront}}</ul>
        {{/phraseFront}}
        {{#sentenceFront}}
            <hr style="height:1px;border:none;border-top:1px dashed #0066CC;background-color:#ffffff;">
            例句：
            <ol>{{sentenceFront}}</ol>
        {{/sentenceFront}}
        {{#BrEPron}}{{BrEPron}}{{/BrEPron}}
        {{#AmEPron}}{{AmEPron}}{{/AmEPron}}
    '''
    cardTemplate['afmt'] = '''
        <table>
            <tr>
                <td><h1 class="term">{{term}}</h1><br><div> 英 [{{BrEPhonetic}}] 美 [{{AmEPhonetic}}]</div></div></td>
                <td><img {{image}} height="120px"></td>
            </tr>
        </table>
        <hr>
        释义：
        <div class='definition'>{{definition}}</div>
        {{#phraseBack}}
            <hr style="height:1px;border:none;border-top:1px dashed #0066CC;background-color:#ffffff;">
            短语：
            <ul class='phrase'>{{phraseBack}}</ul>
        {{/phraseBack}}
        {{#sentenceBack}}
            <hr style="height:1px;border:none;border-top:1px dashed #0066CC;background-color:#ffffff;">
            例句：
            <ol class='sentence'>{{sentenceBack}}</ol>
        {{/sentenceBack}}
    '''
    modelObject['css'] = '''
        .card {
            font-family: arial;
            font-size: 16px;
            text-align: left;
            color: black;
            background-color: white;
        }
        .term {
            font-size : 35px;
        }
        .answer {
            color: green;
	}
        .key {
            color: red;
        }
    '''
    mw.col.models.addTemplate(modelObject, cardTemplate)


def addNoteToDeck(deckObject, modelObject, currentConfig: dict, oneQueryResult: dict):
    if not oneQueryResult:
        logger.warning(f'查询结果{oneQueryResult} 异常，忽略')
        return
    modelObject['did'] = deckObject['id']

    newNote = anki.notes.Note(mw.col, modelObject)
    newNote['term'] = oneQueryResult['term']
    for configName in BASIC_OPTION + EXTRA_OPTION:
        logger.debug(f'字段:{configName}--结果:{oneQueryResult.get(configName)}')
        if oneQueryResult.get(configName):
            # 短语例句
            if configName in ['sentence', 'phrase'] and currentConfig[configName]:
                newNote[f'{configName}Front'] = '\n'.join([f'<li>{e.strip()}</li>' for e, _ in oneQueryResult[configName]])
                newNote[f'{configName}Back'] = '\n'.join([f'<li>{e.strip()}<br/><span class="answer">{c.strip()}</span></li>' for e, c in oneQueryResult[configName]])
            # 图片
            elif configName == 'image':
                newNote[configName] = f'src="{oneQueryResult[configName]}"'
            # 释义
            elif configName == 'definition' and currentConfig[configName]:
                newNote[configName] = '<br/>'.join(oneQueryResult[configName])
            # 发音
            elif configName in EXTRA_OPTION[:2]:
                if currentConfig[configName]:
                    newNote[configName] = f"[sound:{configName}_{oneQueryResult['term']}.mp3]"
            # 其他
            elif currentConfig[configName]:
                newNote[configName] = oneQueryResult[configName]

    mw.col.addNote(newNote)
    mw.col.reset()
    logger.info(f"添加笔记{newNote['term']}")
