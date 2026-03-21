function getSlideLinkedMediaUrls(presentationId, slideObjectId) {
  var presentation = SlidesApp.openById(presentationId);
  var slides = presentation.getSlides();
  var targetSlide = null;
  for (var i = 0; i < slides.length; i++) {
    if (slides[i].getObjectId() === slideObjectId) {
      targetSlide = slides[i];
      break;
    }
  }
  if (!targetSlide) {
    return [];
  }

  var results = [];

  function pushLinkedElement(pageElement, linkedKind) {
    if (!pageElement) {
      return;
    }
    var link = null;
    try {
      link = pageElement.getLink();
    } catch (err) {
      link = null;
    }
    if (!link) {
      return;
    }
    var linkedUrl = '';
    try {
      linkedUrl = link.getUrl();
    } catch (err) {
      linkedUrl = '';
    }
    if (!linkedUrl) {
      return;
    }
    results.push({
      element_id: pageElement.getObjectId(),
      linked_url: linkedUrl,
      linked_kind: linkedKind || '',
    });
  }

  function walkPageElements(pageElements) {
    for (var i = 0; i < pageElements.length; i++) {
      var element = pageElements[i];
      var elementType = element.getPageElementType();
      if (elementType === SlidesApp.PageElementType.GROUP) {
        walkPageElements(element.asGroup().getChildren());
        continue;
      }
      if (elementType === SlidesApp.PageElementType.IMAGE) {
        pushLinkedElement(element.asImage(), 'audio');
        continue;
      }
      if (elementType === SlidesApp.PageElementType.VIDEO) {
        pushLinkedElement(element.asVideo(), 'video');
      }
    }
  }

  walkPageElements(targetSlide.getPageElements());
  return results;
}
