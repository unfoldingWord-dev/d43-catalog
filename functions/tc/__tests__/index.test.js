import {handle} from '../';
import nock from '../__mocks__/nocks';

describe('Main handle', ()=> {
  beforeAll(()=>{
    nock()
  })
  
  it('should correctly fetch API catalog and parse the subject catagories', () => {
    return handle(null, null, (err, res) => {
      expect(err).toBeFalsy();
      expect(res).toBe('OK')
    });
  })
})