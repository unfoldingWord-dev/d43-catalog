function pivotOnKey(catalog, key) {
  const index = [];
  const newCatalog = {};
  const pluralKey = key + 's';
  const pivoted = {
    catalogs: catalog.catalogs,
    [pluralKey]: []
  };
  catalog.languages.forEach(
    ({identifier: language, resources, ...otherLanguage}) => {
      resources.forEach((resource, resourceIndex) => {
        const pivotKeyValue = resource[key].replace(/\s/ig, '_');
        if (pivotKeyValue) {
          const indexURL = `https://api.door43.org/v3/${pluralKey}/${pivotKeyValue}.json`;
          if (!newCatalog[pivotKeyValue]) newCatalog[pivotKeyValue] = [];
          newCatalog[pivotKeyValue].push(
            Object.assign({
            [key]:pivotKeyValue,
            identifier: pivotKeyValue,
            language,
            resources: [resources[resourceIndex]]
          }, otherLanguage));
          if (!index.find(url => url === indexURL)) {
            index.push(indexURL);
          }
          pivoted[pluralKey].push(
            Object.assign({
            [key]:pivotKeyValue,
            identifier: pivotKeyValue,
            language,
            resources: [resources[resourceIndex]]
          }, otherLanguage));
        }
      });
    });
  return {
    [key]: newCatalog,
    index,
    pivoted
  };
}

module.exports = {
  pivotOnKey
}