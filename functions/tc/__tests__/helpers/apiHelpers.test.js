import apiHelpers from '../../helpers/apiHelpers';
import nock from '../../__mocks__/nocks';

describe('apiHelpers.getCatalog', () => {
  beforeAll(() => {
    nock();
  })

  it('should successfully fetch the latest catalog', async () => {
    const catalog = await apiHelpers.getCatalog();
    expect(catalog).toMatchObject({
      catalogs: expect.arrayContaining([
        expect.objectContaining({
          identifier: 'langnames',
          modified: '2016-10-03',
          url: 'https://td.unfoldingword.org/exports/langnames.json'
        })
      ]),
      languages: expect.arrayContaining([
        expect.objectContaining({
          direction: 'ltr',
          identifier: 'hi',
          resources: expect.arrayContaining([
            expect.objectContaining({
              subject: expect.any(String)
            })
          ]),
          title: 'हिन्दी'
        })
      ])
    })
  })

});

describe('apiHelpers.makeRequest', () => {
  beforeAll(() => {
    nock();
  })

  it('should successfully fetch a url', async () => {
    const res = await apiHelpers.makeRequest('https://google.com');
    expect(res).toBe('OK');
  })
})

describe('apiHelpers.uploadToS3', () => {
  beforeAll(() => {
    nock();
  })

  it('should successfully upload to s3', () => {
    return apiHelpers.uploadToS3('hello/world/data.json', {a:'1'}).then((res)=>{
      expect(res).toBe();
    })
  })
})

