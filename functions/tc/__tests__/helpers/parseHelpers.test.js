import {parseCatalogOnResourceKey} from '../../helpers/parseHelpers';
const catalog = require('../fixtures/catalog.json')

describe('parseHelpers.parseCatalogOnResourceKey', () => {
  it('should successfully create an index, pivoted, and subject object structure', () => {
    const {pivoted, index, subject} = parseCatalogOnResourceKey(catalog, 'subject');
    expect(index).toMatchObject(['https://api.door43.org/v3/subjects/Translation_Notes.json']);
    expect(pivoted).toMatchObject({
      catalogs:
        [{
          identifier: 'langnames',
          modified: '2016-10-03',
          url: 'https://td.unfoldingword.org/exports/langnames.json'
        }],
      subjects:
        [{
          subject: 'Translation_Notes',
          identifier: 'Translation_Notes',
          language: 'ur-deva',
          resources: expect.any(Array),
          direction: 'ltr'
        }]
    })
    expect(subject).toMatchObject({
      Translation_Notes:
        [{
          subject: 'Translation_Notes',
          identifier: 'Translation_Notes',
          language: 'ur-deva',
          resources: expect.any(Array),
          direction: 'ltr'
        }]
    })
  })
  it('should be empty obejcts if catalog does not return correct JSON', () => {
    const {pivoted, index, subject} = parseCatalogOnResourceKey({}, 'subject');
    expect(pivoted).toMatchObject({ catalogs: [], subjects: [] });
    expect(index).toHaveLength(0);
    expect(subject).toMatchObject({})
  })

  it('should correctly parse based on parameter keys', () => {
    const {pivoted, index, hello} = parseCatalogOnResourceKey({}, 'hello');
    expect(pivoted).toMatchObject({ catalogs: [], hellos: [] });
    expect(index).toHaveLength(0);
    expect(hello).toMatchObject({})
  })
})