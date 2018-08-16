function pivotOnKey(catalog, key) {
  const index = [];
  const newCatalog = {};
  const pivoted = {
    catalogs: catalog.catalogs,
    [key]: []
  };
  catalog.languages.forEach(
    ({identifier: language, resources, ...otherLanguage}) => {
      resources.forEach((resource, resourceIndex) => {
        const pivotKeyValue = resource[key].replace(/\s/ig, '_');
        if (pivotKeyValue) {
          const indexURL = `https://api.door43.org/v3/${key}s/${pivotKeyValue}.json`;
          if (!newCatalog[pivotKeyValue]) newCatalog[pivotKeyValue] = [];
          newCatalog[pivotKeyValue].push({
            [key]:pivotKeyValue,
            identifier: pivotKeyValue,
            language,
            ...otherLanguage,
            resources: [resources[resourceIndex]]
          });
          if (!index.find(url => url === indexURL)) {
            index.push(indexURL);
          }
          pivoted[key].push({
            [key]:pivotKeyValue,
            identifier: pivotKeyValue,
            language,
            ...otherLanguage,
            resources: [resources[resourceIndex]]
          });
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